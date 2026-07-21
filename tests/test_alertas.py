"""Testes da spec 004 — Motor de Alertas Preventivos e Agendamento.

Critério de aceite do kanban (FR-008/SC-006): os dois gatilhos, a idempotência e o
caso `dados_insuficientes` têm teste automatizado. Cobertura por user story:

- US1 (gatilho km, P1): dispara vinculado ao `limiar_id`, não dispara abaixo da janela,
  e reage à **edição de limiar ao vivo** sem cache de processo (SC-004/FR-002).
- US2 (gatilho tempo, P1): dispara vinculado ao `limiar_id`; não dispara dentro do prazo.
- US3 (idempotência/histórico, P2): 10 execuções → zero duplicatas (SC-002); o motor não
  escreve staging nem `log_qualidade` (FR-007); resolvido permanece e a condição reincidente
  cria nova linha `ativo` (histórico permanente, FR-004).
- US4 (dados_insuficientes, P2): sem manutenção, km não confiável e sem limiar para o
  `tipo_veiculo` viram **um** alerta por veículo com `limiar_id` NULL (SC-003); coexistem com
  os gatilhos sem suprimi-los.

Injeta `hoje` (relógio determinístico — contrato § Invocação) e lê os limiares reais de
`limiar_config` (semeados por db.init_db) em vez de valores mágicos.
"""

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select, text as sql_text, update
from sqlalchemy.orm import Session

import db.config
import db.init_db
from alertas.motor import verificar_alertas
from alertas.regras import dispara_km, dispara_tempo, km_confiavel
from alertas.resolver import resolver_alerta
from db.models import Alerta, LimiarConfig, Manutencao, Veiculo

RAIZ = Path(__file__).resolve().parents[1]
HOJE = date(2026, 7, 20)

# Placas canônicas (ADR-001) usadas nos testes — validadas pelo hook do ORM
PLACA_A = "RLL8062"   # veículo A da demo (gatilho km)
PLACA_B = "TND8453"   # veículo B da demo (gatilho tempo)
PLACA_C = "ABC1D23"   # Mercosul, auxiliar


@pytest.fixture
def ambiente_motor(tmp_path, monkeypatch):
    """Banco limpo em tmp_path com esquema + limiares semeados (db.init_db.main()).
    Espelha a fixture de tests/test_pipeline.py::ambiente_pipeline."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/frota.db")
    db.config.reset_engine()
    db.init_db.main()
    yield db.config.get_engine()
    db.config.reset_engine()


# ---------- helpers ----------

def _limiar(engine, tipo_veiculo, tipo_manutencao):
    """Limiar real de `limiar_config` (semeado dos seeds) — sem valores mágicos."""
    with engine.connect() as c:
        return c.execute(
            select(LimiarConfig).where(
                LimiarConfig.tipo_veiculo == tipo_veiculo,
                LimiarConfig.tipo_manutencao == tipo_manutencao,
            )
        ).one()


def _semear(engine, placa, tipo_veiculo, km_atual, manutencoes=()):
    """Insere um veículo e suas manutenções (parent antes do child — FK)."""
    with Session(engine) as s:
        s.add(Veiculo(placa=placa, tipo_veiculo=tipo_veiculo,
                      km_atual=km_atual, fonte_origem="teste"))
        s.flush()
        for m in manutencoes:
            s.add(Manutencao(
                placa=placa, tipo=m["tipo"], data=m["data"],
                categoria=m.get("categoria", "preventiva"),
                km_no_momento=m.get("km_no_momento"), fonte_origem="teste",
            ))
        s.commit()


def _conta(engine, **filtros):
    """Conta linhas de `alerta` com os filtros de igualdade dados (None → IS NULL)."""
    stmt = select(func.count()).select_from(Alerta.__table__)
    for col, val in filtros.items():
        stmt = stmt.where(getattr(Alerta, col) == val)
    with engine.connect() as c:
        return c.execute(stmt).scalar()


def _um_alerta(engine, **filtros):
    """Retorna o único alerta que casa com os filtros (falha se não for exatamente 1)."""
    stmt = select(Alerta)
    for col, val in filtros.items():
        stmt = stmt.where(getattr(Alerta, col) == val)
    with Session(engine) as s:
        return s.scalars(stmt).one()


# ---------- Regras puras (alertas/regras.py — T005, sem banco) ----------

@pytest.mark.parametrize(("km_atual", "km_no_momento", "esperado"), [
    (54600, 50000, True),    # leitura normal, crescente
    (50000, 50000, True),    # igual — odômetro não andou para trás, ainda confiável
    (49999, 50000, False),   # leitura decrescente → não confiável (ADR-002)
    (54600, None, False),    # sem km_no_momento na última manutenção
    (0, 0, False),           # km_atual não positivo (R5 exige > 0)
    (None, 50000, False),    # km_atual ausente
])
def test_regras_km_confiavel(km_atual, km_no_momento, esperado):
    assert km_confiavel(km_atual, km_no_momento) is esperado


@pytest.mark.parametrize(("km_desde", "limite_km", "antecedencia_km", "esperado"), [
    (4500, 5000, 500, True),    # exatamente na janela (limite − antecedencia)
    (4499, 5000, 500, False),   # 1 km abaixo da janela
    (9999, 5000, 500, True),    # bem acima
])
def test_regras_dispara_km(km_desde, limite_km, antecedencia_km, esperado):
    assert dispara_km(km_desde, limite_km, antecedencia_km) is esperado


@pytest.mark.parametrize(("dias_desde", "limite_dias", "antecedencia_dias", "esperado"), [
    (165, 180, 15, True),    # exatamente na janela
    (164, 180, 15, False),   # 1 dia abaixo
    (400, 180, 15, True),    # bem acima
])
def test_regras_dispara_tempo(dias_desde, limite_dias, antecedencia_dias, esperado):
    assert dispara_tempo(dias_desde, limite_dias, antecedencia_dias) is esperado


# ---------- Contrato do retorno (motor_alertas.md § Retorno) ----------

def test_contrato_chaves_do_retorno(ambiente_motor):
    """Contrato § Retorno: `verificar_alertas()` devolve EXATAMENTE as 5 chaves de
    diagnóstico — sem sobra nem falta (estabilidade do contrato)."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_km = L.limite_km - L.antecedencia_km
    _semear(engine, PLACA_A, "leve", km_atual=50000 + janela_km + 100, manutencoes=[
        {"tipo": "troca_oleo", "data": HOJE - timedelta(days=30), "km_no_momento": 50000},
    ])

    resumo = verificar_alertas(engine, hoje=HOJE)

    assert set(resumo) == {
        "veiculos_avaliados",
        "criados_km",
        "criados_tempo",
        "criados_dados_insuficientes",
        "ja_ativos",
    }
    assert all(isinstance(v, int) for v in resumo.values())
    assert resumo["veiculos_avaliados"] == 1  # 1 veículo percorrido


# ---------- US1: gatilho por km (P1) ----------

def test_us1_gatilho_km_dispara_e_vincula_limiar(ambiente_motor):
    """US1.1: km_atual − km_no_momento ≥ limite_km − antecedencia_km → alerta `km`
    vinculado ao `limiar_id` do par (tipo_veiculo, tipo_manutencao)."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_km = L.limite_km - L.antecedencia_km
    km_base = 50000
    _semear(engine, PLACA_A, "leve", km_atual=km_base + janela_km + 100, manutencoes=[
        {"tipo": "troca_oleo", "data": HOJE - timedelta(days=30), "km_no_momento": km_base},
    ])

    resumo = verificar_alertas(engine, hoje=HOJE)

    assert resumo["criados_km"] == 1
    assert _conta(engine, placa=PLACA_A, tipo_gatilho="km") == 1
    alerta = _um_alerta(engine, placa=PLACA_A, tipo_gatilho="km")
    assert alerta.limiar_id == L.id
    assert alerta.situacao == "ativo"


def test_us1_gatilho_km_nao_dispara_abaixo_da_janela(ambiente_motor):
    """US1.2: abaixo da janela de antecedência → nenhum alerta `km`."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_km = L.limite_km - L.antecedencia_km
    km_base = 50000
    _semear(engine, PLACA_A, "leve", km_atual=km_base + janela_km - 100, manutencoes=[
        {"tipo": "troca_oleo", "data": HOJE - timedelta(days=30), "km_no_momento": km_base},
    ])

    verificar_alertas(engine, hoje=HOJE)

    assert _conta(engine, placa=PLACA_A, tipo_gatilho="km") == 0


def test_us1_sc004_edicao_limiar_ao_vivo_sem_cache(ambiente_motor):
    """SC-004/FR-002: editar `limiar_config` altera a PRÓXIMA verificação sem reiniciar
    nem alterar código — prova de que o motor relê o limiar a cada ciclo (sem cache)."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_km = L.limite_km - L.antecedencia_km
    km_base = 50000
    # km_desde = janela − 100: fica logo abaixo da janela atual
    _semear(engine, PLACA_A, "leve", km_atual=km_base + janela_km - 100, manutencoes=[
        {"tipo": "troca_oleo", "data": HOJE - timedelta(days=30), "km_no_momento": km_base},
    ])

    verificar_alertas(engine, hoje=HOJE)
    assert _conta(engine, placa=PLACA_A, tipo_gatilho="km") == 0

    # baixa o limite ao vivo → a janela encolhe e o mesmo km_desde passa a cruzá-la
    with engine.begin() as c:
        c.execute(update(LimiarConfig).where(LimiarConfig.id == L.id)
                  .values(limite_km=janela_km - 200 + L.antecedencia_km))

    verificar_alertas(engine, hoje=HOJE)
    assert _conta(engine, placa=PLACA_A, tipo_gatilho="km") == 1


# ---------- US2: gatilho por tempo (P1) ----------

def test_us2_gatilho_tempo_dispara_e_vincula_limiar(ambiente_motor):
    """US2.1: hoje − data_última ≥ limite_dias − antecedencia_dias → alerta `tempo`.
    km ajustado para NÃO disparar, isolando o gatilho de tempo."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_dias = L.limite_dias - L.antecedencia_dias
    _semear(engine, PLACA_B, "leve", km_atual=33200, manutencoes=[
        {"tipo": "troca_oleo",
         "data": HOJE - timedelta(days=janela_dias + 1),
         "km_no_momento": 33000},  # km_desde=200 << janela_km → sem km
    ])

    resumo = verificar_alertas(engine, hoje=HOJE)

    assert resumo["criados_tempo"] == 1
    assert _conta(engine, placa=PLACA_B, tipo_gatilho="tempo") == 1
    assert _conta(engine, placa=PLACA_B, tipo_gatilho="km") == 0
    alerta = _um_alerta(engine, placa=PLACA_B, tipo_gatilho="tempo")
    assert alerta.limiar_id == L.id
    assert alerta.situacao == "ativo"


def test_us2_gatilho_tempo_nao_dispara_dentro_do_prazo(ambiente_motor):
    """US2.2: dentro do prazo → nenhum alerta `tempo`."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_dias = L.limite_dias - L.antecedencia_dias
    _semear(engine, PLACA_B, "leve", km_atual=33200, manutencoes=[
        {"tipo": "troca_oleo",
         "data": HOJE - timedelta(days=janela_dias - 10),
         "km_no_momento": 33000},
    ])

    verificar_alertas(engine, hoje=HOJE)

    assert _conta(engine, placa=PLACA_B, tipo_gatilho="tempo") == 0


# ---------- US3: idempotência e histórico permanente (P2) ----------

def test_us3_sc002_idempotencia_dez_execucoes(ambiente_motor):
    """SC-002: 10 verificações sobre o mesmo estado → zero duplicatas; da 2ª rodada em
    diante `alertas_criados == 0`."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_km = L.limite_km - L.antecedencia_km
    km_base = 50000
    _semear(engine, PLACA_A, "leve", km_atual=km_base + janela_km + 100, manutencoes=[
        {"tipo": "troca_oleo", "data": HOJE - timedelta(days=30), "km_no_momento": km_base},
    ])

    primeiro = verificar_alertas(engine, hoje=HOJE)
    total_apos_1 = _conta(engine)
    criados_1 = (primeiro["criados_km"] + primeiro["criados_tempo"]
                 + primeiro["criados_dados_insuficientes"])
    assert criados_1 == total_apos_1 > 0
    assert primeiro["ja_ativos"] == 0  # 1ª rodada: nada preexistente

    for _ in range(9):
        resumo = verificar_alertas(engine, hoje=HOJE)
        assert resumo["criados_km"] == 0
        assert resumo["criados_tempo"] == 0
        assert resumo["criados_dados_insuficientes"] == 0
        assert resumo["ja_ativos"] > 0  # todos os candidatos colidem (no-op idempotente)

    assert _conta(engine) == total_apos_1  # nenhuma duplicata em 10 execuções


def test_us3_fr007_nao_escreve_staging_nem_log_qualidade(ambiente_motor):
    """FR-007: o motor conversa só via `alerta`; nunca escreve staging nem log_qualidade."""
    engine = ambiente_motor
    _semear(engine, PLACA_A, "leve", km_atual=99000, manutencoes=[
        {"tipo": "troca_oleo", "data": HOJE - timedelta(days=30), "km_no_momento": 50000},
    ])

    verificar_alertas(engine, hoje=HOJE)

    tabelas = ["stg_abastecimento", "stg_multas", "stg_manutencao",
               "stg_licenciamento", "log_qualidade"]
    with engine.connect() as c:
        for t in tabelas:
            assert c.execute(sql_text(f"SELECT COUNT(*) FROM {t}")).scalar() == 0, t


def test_us3_historico_permanente_e_recorrencia(ambiente_motor):
    """US3.2/US3.3/FR-004: alerta resolvido permanece (nunca DELETE) e a condição
    reincidente cria NOVA linha `ativo` — o índice parcial só enxerga ativos."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_km = L.limite_km - L.antecedencia_km
    _semear(engine, PLACA_A, "leve", km_atual=50000 + janela_km + 100, manutencoes=[
        {"tipo": "troca_oleo", "data": HOJE - timedelta(days=30), "km_no_momento": 50000},
    ])

    verificar_alertas(engine, hoje=HOJE)
    alerta = _um_alerta(engine, placa=PLACA_A, tipo_gatilho="km")
    aid = alerta.id

    # resolução é ação externa (create-only): resolver_alerta muda apenas a situação
    assert resolver_alerta(engine, aid) is True
    assert resolver_alerta(engine, 999_999) is False

    # condição persiste → nova linha ativa; a resolvida NÃO some
    verificar_alertas(engine, hoje=HOJE)

    assert _conta(engine, placa=PLACA_A, tipo_gatilho="km") == 2
    assert _conta(engine, placa=PLACA_A, tipo_gatilho="km", situacao="ativo") == 1
    assert _conta(engine, id=aid, situacao="resolvido") == 1  # histórico preservado


# ---------- US4: dados insuficientes viram alerta, não silêncio (P2) ----------

def test_us4_sc003_dados_insuficientes_sem_manutencao(ambiente_motor):
    """US4.1/SC-003: veículo com tipos aplicáveis mas SEM manutenção → exatamente UM
    `dados_insuficientes` com `limiar_id` NULL e `detalhe` não-vazio."""
    engine = ambiente_motor
    _semear(engine, PLACA_A, "leve", km_atual=40000, manutencoes=[])

    resumo = verificar_alertas(engine, hoje=HOJE)

    assert _conta(engine, placa=PLACA_A, tipo_gatilho="dados_insuficientes") == 1
    di = _um_alerta(engine, placa=PLACA_A, tipo_gatilho="dados_insuficientes")
    assert di.limiar_id is None
    assert di.detalhe  # não-vazio: enumera as causas
    assert resumo["veiculos_avaliados"] >= 1


def test_us4_dados_insuficientes_km_nao_confiavel(ambiente_motor):
    """US4.2: leitura de odômetro decrescente (km_atual < km_no_momento) → km não
    confiável → `dados_insuficientes` com a causa no `detalhe` (ADR-002)."""
    engine = ambiente_motor
    _semear(engine, PLACA_A, "leve", km_atual=50000, manutencoes=[
        {"tipo": "troca_oleo", "data": HOJE - timedelta(days=30), "km_no_momento": 60000},
    ])

    verificar_alertas(engine, hoje=HOJE)

    assert _conta(engine, placa=PLACA_A, tipo_gatilho="dados_insuficientes") == 1
    di = _um_alerta(engine, placa=PLACA_A, tipo_gatilho="dados_insuficientes")
    assert di.limiar_id is None
    assert "km não confiável" in di.detalhe
    assert _conta(engine, placa=PLACA_A, tipo_gatilho="km") == 0


def test_us4_dados_insuficientes_sem_limiar_para_tipo_veiculo(ambiente_motor):
    """Edge case: `tipo_veiculo` sem NENHUM limiar → veículo não-avaliável vira
    `dados_insuficientes` (nunca é pulado em silêncio)."""
    engine = ambiente_motor
    with engine.begin() as c:
        c.execute(sql_text("DELETE FROM limiar_config WHERE tipo_veiculo = 'caminhao'"))
    _semear(engine, PLACA_C, "caminhao", km_atual=120000, manutencoes=[])

    resumo = verificar_alertas(engine, hoje=HOJE)

    assert _conta(engine, placa=PLACA_C, tipo_gatilho="dados_insuficientes") == 1
    di = _um_alerta(engine, placa=PLACA_C, tipo_gatilho="dados_insuficientes")
    assert di.limiar_id is None
    assert resumo["criados_dados_insuficientes"] >= 1


def test_us4_coexistencia_gatilho_e_dados_insuficientes(ambiente_motor):
    """US4.3: um tipo avaliável e vencido (gera `tempo`) + outros tipos sem histórico →
    coexistem o alerta do gatilho e UM `dados_insuficientes` (gatilhos distintos)."""
    engine = ambiente_motor
    L = _limiar(engine, "leve", "troca_oleo")
    janela_dias = L.limite_dias - L.antecedencia_dias
    _semear(engine, PLACA_B, "leve", km_atual=33200, manutencoes=[
        {"tipo": "troca_oleo",
         "data": HOJE - timedelta(days=janela_dias + 1),
         "km_no_momento": 33000},
    ])

    verificar_alertas(engine, hoje=HOJE)

    assert _conta(engine, placa=PLACA_B, tipo_gatilho="tempo") == 1
    assert _conta(engine, placa=PLACA_B, tipo_gatilho="dados_insuficientes") == 1


# ---------- US5: ciclo agendado de ponta a ponta (P1) ----------

def _veiculo_demo(tipo_gatilho: str) -> dict:
    """Veículo de demo dos seeds (sem valores mágicos no teste)."""
    veiculos = json.loads((RAIZ / "data" / "seeds" / "veiculos.json").read_text())
    return next(v for v in veiculos
                if v.get("demo_gatilho") and v.get("demo_gatilho_tipo") == tipo_gatilho)


@pytest.fixture
def ambiente_ciclo(tmp_path, monkeypatch):
    """Ambiente completo do ciclo (ETL + motor) — espelha tests/test_pipeline.py::
    ambiente_pipeline: banco limpo, inbox isolado com o CSV de abastecimento, API de multas
    simulada por monkeypatch de httpx.get (sem servidor)."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/frota.db")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    shutil.copy(RAIZ / "data" / "seeds" / "abastecimento.csv", inbox / "abastecimento.csv")
    monkeypatch.setenv("PIPELINE_INBOX", str(inbox))
    monkeypatch.setenv("MULTAS_API_URL", "http://fake-teste:8000")

    payload = (RAIZ / "fake_api" / "multas.json").read_bytes()
    monkeypatch.setattr(httpx, "get", lambda url, timeout=None: httpx.Response(
        200, content=payload, request=httpx.Request("GET", url)))

    db.config.reset_engine()
    db.init_db.main()
    yield db.config.get_engine()
    db.config.reset_engine()


def test_us5_sc005_intervalo_por_env_var(monkeypatch):
    """SC-005: o intervalo do ciclo vem de env var (zero código); default 90; valor
    inválido/≤0 recai no default."""
    from alertas.alert_config import intervalo_ciclo_segundos

    monkeypatch.delenv("CICLO_INTERVALO_SEGUNDOS", raising=False)
    assert intervalo_ciclo_segundos() == 90        # default
    monkeypatch.setenv("CICLO_INTERVALO_SEGUNDOS", "5")
    assert intervalo_ciclo_segundos() == 5         # override (demo 1–2 min)
    monkeypatch.setenv("CICLO_INTERVALO_SEGUNDOS", "lixo")
    assert intervalo_ciclo_segundos() == 90        # inválido → default
    monkeypatch.setenv("CICLO_INTERVALO_SEGUNDOS", "-3")
    assert intervalo_ciclo_segundos() == 90        # ≤0 → default


def test_us5_ciclo_ordenado_deposita_csv_dispara_alerta_km(ambiente_ciclo):
    """US5.1/SC-001: depositar o CSV de gatilho da spec 001 → no ciclo seguinte o ETL
    ingere o km novo E o motor dispara o alerta km, sem passo manual (ordem ETL→motor)."""
    from pipeline.config import inbox_dir
    from scheduler import executar_ciclo_e_verificar

    engine = ambiente_ciclo
    demo = _veiculo_demo("km")

    executar_ciclo_e_verificar(hoje=HOJE)  # ciclo baseline: ainda sem alerta km da demo
    assert _conta(engine, placa=demo["placa"], tipo_gatilho="km") == 0

    # gesto da demo: depositar o gatilho na pasta monitorada
    shutil.copy(RAIZ / "data" / "seeds" / "gatilho_demo_abastecimento.csv",
                inbox_dir() / "gatilho_demo_abastecimento.csv")
    resumo = executar_ciclo_e_verificar(hoje=HOJE)

    assert resumo["motor"]["criados_km"] >= 1
    assert _conta(engine, placa=demo["placa"], tipo_gatilho="km") == 1
    alerta = _um_alerta(engine, placa=demo["placa"], tipo_gatilho="km")
    assert alerta.limiar_id is not None and alerta.situacao == "ativo"


def test_us5_fonte_indisponivel_nao_bloqueia_motor(ambiente_ciclo, monkeypatch):
    """US5.3/SC-005 (herdada da spec 003): uma fonte do ETL fora do ar não impede a
    verificação de alertas sobre o estado consolidado disponível."""
    from scheduler import executar_ciclo_e_verificar

    def _fora_do_ar(url, timeout=None):
        raise httpx.ConnectError("simulado: API de multas fora do ar")

    monkeypatch.setattr(httpx, "get", _fora_do_ar)
    resumo = executar_ciclo_e_verificar(hoje=HOJE)

    assert resumo["etl"]["multas"]["situacao"] == "indisponivel"  # fonte caiu
    assert resumo["motor"]["veiculos_avaliados"] > 0              # motor rodou mesmo assim
