"""Testes da spec 003 — Pipeline ETL de Integração das Fontes.

T010: testes unitários dos normalizadores (research R5/R6) — placa dual (ADR-001),
datas nos 3 formatos (incluindo serial Excel), decimais com vírgula e as grafias de
tipo/categoria catalogadas em data/seeds/INCONSISTENCIAS.md.

T016: aceitação da US1 — 1 ciclo popula os 4 stagings com bruto intacto + carimbo
de carga + fonte_origem com hash (R1); 2º ciclo sem novidade não acrescenta nada.

T021/T022: aceitação da US2 (SC-002) — inconsistências da spec 001 normalizadas ou
rejeitadas com motivo; conservação por fonte; lote parcialmente corrompido nunca é
tudo-ou-nada; cnh sintética jamais chega a uma consolidada (FR-011).

T024/T025: aceitação da US3 (SC-001) — dupla execução com estado idêntico (consolidadas,
staging e log); reprocessar lote antigo é no-op; momento da demo (gatilho eleva km_atual
— R10/FR-010) e arquivo renomeado com mesmo conteúdo não muda nada.

T027: aceitação da US4 (SC-005) — fonte fora do ar não derruba o ciclo: as demais
processam 100%, a falha vai a log_qualidade (fonte_indisponivel, R8) e o ciclo
seguinte se recupera sozinho quando a fonte volta.

Follow-up do ciclo 1 da revisão SDD (BUG-1 + lacuna do invariante negativo):
regressão do payload de multas novo-mas-vazio (disponível ≠ indisponível) e testes
e2e conduzindo os motivos defense-in-depth (tipo/categoria/situacao_desconhecida e
inválidos numéricos/data por fonte) pelo pipeline até o log_qualidade.
"""

import json
import re
import shutil
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pandas as pd
import pytest
from sqlalchemy import func, text as sql_text

import db.config
import db.init_db
from pipeline.transform.normalizadores import (
    converter_decimal,
    converter_int,
    interpretar_data,
    normalizar_categoria,
    normalizar_placa,
    normalizar_situacao,
    normalizar_tipo_manutencao,
)


# ---------- Placa canônica (ADR-001) ----------


@pytest.mark.parametrize(
    ("bruto", "canonica"),
    [
        ("RLL-8062", "RLL8062"),      # antigo com hífen (Fonte 1)
        ("xyz1234", "XYZ1234"),       # antigo minúsculo
        ("oll2d58", "OLL2D58"),       # Mercosul minúsculo (Fonte 2)
        ("ABC 1D23", "ABC1D23"),      # com espaço
        ("ABC1D23", "ABC1D23"),       # já canônica
    ],
)
def test_placa_normalizavel(bruto, canonica):
    assert normalizar_placa(bruto) == canonica


@pytest.mark.parametrize("bruto", ["AB-123", "1234567", "ABCD123", "", None, "ABC12345"])
def test_placa_invalida_vira_none(bruto):
    assert normalizar_placa(bruto) is None


# ---------- Datas: 3 formatos, ordem fixa, sem fuzzy (R5) ----------


@pytest.mark.parametrize(
    ("bruto", "esperada"),
    [
        ("28/11/2025", date(2025, 11, 28)),   # dd/mm/aaaa (Fonte 1)
        ("2025-11-20", date(2025, 11, 20)),   # ISO (Fontes 1–4)
        ("46068", date(2026, 2, 15)),         # serial Excel, origem 1899-12-30 (Fontes 3–4)
    ],
)
def test_data_interpretavel(bruto, esperada):
    assert interpretar_data(bruto) == esperada


@pytest.mark.parametrize(
    "bruto",
    [
        "31/02/2026",   # dia inexistente
        "amanha",       # lixo
        "99999",        # serial fora da faixa 20.000–80.000
        "13/2025",      # incompleta
        "",             # vazia → chamador decide data_ausente
        None,
    ],
)
def test_data_nao_interpretavel_vira_none(bruto):
    assert interpretar_data(bruto) is None


# ---------- Decimais e inteiros ----------


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("31,5", Decimal("31.5")),        # vírgula decimal (Fonte 1)
        ("350,75", Decimal("350.75")),
        ("280.50", Decimal("280.50")),    # ponto decimal (Fonte 3)
    ],
)
def test_decimal_convertido(bruto, esperado):
    assert converter_decimal(bruto) == esperado


@pytest.mark.parametrize("bruto", ["abc", "-1", "", None])
def test_decimal_invalido_vira_none(bruto):
    assert converter_decimal(bruto) is None


def test_int_km():
    assert converter_int("4400") == 4400


@pytest.mark.parametrize("bruto", ["", None])
def test_int_ausente_vira_none(bruto):
    # km ausente é válido (coluna nullable, ADR-002) — motivo é juízo do chamador
    assert converter_int(bruto) is None


@pytest.mark.parametrize("bruto", ["4400.0", "abc", "-10"])
def test_int_invalido_vira_none(bruto):
    assert converter_int(bruto) is None


# ---------- Vocabulários (R6 — grafias de INCONSISTENCIAS.md) ----------


@pytest.mark.parametrize(
    ("bruto", "canonico"),
    [
        ("troca de oleo", "troca_oleo"),
        ("Troca Óleo", "troca_oleo"),
        ("TROCA_OLEO", "troca_oleo"),
        ("FILTROS", "filtros"),
        ("PNEUS", "pneus"),
        ("REVISAO 10000", "revisao_geral"),
        ("REVISAO 60000", "revisao_geral"),
        ("Revisão 10.000 km", "revisao_geral"),
    ],
)
def test_tipo_manutencao_normalizado(bruto, canonico):
    assert normalizar_tipo_manutencao(bruto) == canonico


@pytest.mark.parametrize("bruto", ["lavagem", "", None])
def test_tipo_desconhecido_vira_none(bruto):
    assert normalizar_tipo_manutencao(bruto) is None


@pytest.mark.parametrize(
    ("bruto", "canonica"),
    [
        ("Preventiva", "preventiva"),
        ("prev.", "preventiva"),
        ("CORRETIVA", "corretiva"),
        ("corretiva", "corretiva"),
    ],
)
def test_categoria_normalizada(bruto, canonica):
    assert normalizar_categoria(bruto) == canonica


@pytest.mark.parametrize("bruto", ["outra", "", None])
def test_categoria_desconhecida_vira_none(bruto):
    assert normalizar_categoria(bruto) is None


def test_situacao_pertence_ao_check():
    assert normalizar_situacao("Pendente", {"pendente", "paga"}) == "pendente"
    assert normalizar_situacao("em_dia", {"em_dia", "vencido"}) == "em_dia"


def test_situacao_fora_do_check_vira_none():
    # defesa em profundidade — a fonte já padroniza (contratos da spec 001)
    assert normalizar_situacao("cancelada", {"pendente", "paga"}) is None
    assert normalizar_situacao(None, {"pendente", "paga"}) is None


# ---------- T016: aceitação US1 — extração bruta com rastreabilidade ----------

RAIZ = Path(__file__).resolve().parents[1]
STAGING = ["stg_abastecimento", "stg_multas", "stg_manutencao", "stg_licenciamento"]
FONTE_ORIGEM_RE = re.compile(r".+@sha256:[0-9a-f]{12}$")
VOCABULARIO_SITUACAO = {"ok", "sem_novidade", "indisponivel"}


@pytest.fixture
def ambiente_pipeline(tmp_path, monkeypatch):
    """Banco limpo + inbox isolado + API de multas simulada (sem servidor):
    monkeypatch de httpx.get devolvendo o multas.json real da fake_api."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/frota.db")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    shutil.copy(RAIZ / "data" / "seeds" / "abastecimento.csv", inbox / "abastecimento.csv")
    monkeypatch.setenv("PIPELINE_INBOX", str(inbox))
    monkeypatch.setenv("MULTAS_API_URL", "http://fake-teste:8000")

    payload = (RAIZ / "fake_api" / "multas.json").read_bytes()

    def _get(url, timeout=None):
        return httpx.Response(200, content=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", _get)
    db.config.reset_engine()
    db.init_db.main()
    yield db.config.get_engine()
    db.config.reset_engine()


def _contagens_staging(engine) -> dict[str, int]:
    with engine.connect() as c:
        return {t: c.execute(sql_text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in STAGING}


def test_us1_ciclo_popula_staging_bruto_com_rastreabilidade(ambiente_pipeline):
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    resumo = executar_ciclo()

    # resumo respeita o contrato (chaves e vocabulário — ciclo_pipeline.md § Retorno)
    for fonte, r in resumo.items():
        assert set(r) == {"situacao", "extraidos", "consolidados", "rejeitados"}, fonte
        assert r["situacao"] in VOCABULARIO_SITUACAO, (fonte, r["situacao"])

    contagens = _contagens_staging(engine)
    assert all(n > 0 for n in contagens.values()), contagens

    with engine.connect() as c:
        # carimbo de carga + fonte_origem com hash em 100% dos stagings (FR-002, R1)
        for t in STAGING:
            assert c.execute(sql_text(f"SELECT COUNT(*) FROM {t} WHERE carga_em IS NULL")).scalar() == 0, t
            origens = [r[0] for r in c.execute(sql_text(f"SELECT DISTINCT fonte_origem FROM {t}"))]
            assert origens and all(FONTE_ORIGEM_RE.match(o) for o in origens), (t, origens)

        # cenário 1: CSV bruto intacto — hífen e vírgula decimal preservados
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM stg_abastecimento WHERE placa LIKE '%-%'")).scalar() > 0
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM stg_abastecimento WHERE litros LIKE '%,%'")).scalar() > 0

        # cenário 2: endpoint como origem; bruto retém minúsculas e a cnh sintética
        origem_multas = c.execute(sql_text(
            "SELECT DISTINCT fonte_origem FROM stg_multas")).scalar()
        assert "/multas@sha256:" in origem_multas
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM stg_multas WHERE placa GLOB '[a-z]*'")).scalar() > 0
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM stg_multas WHERE cnh IS NOT NULL")).scalar() > 0

        # cenário 3: todas as abas relevantes do XLSX, sem serial corrompido por float
        abas = {r[0] for r in c.execute(sql_text("SELECT DISTINCT aba_origem FROM stg_manutencao"))}
        assert abas == {"Oficina Central", "Oficina Regional Norte", "Manutenção Terceirizada"}
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM stg_manutencao WHERE data LIKE '%.0'")).scalar() == 0

        # cenário 4: duplicatas do legado chegam ao staging (dedup é do transform)
        duplicadas = c.execute(sql_text(
            "SELECT COUNT(*) FROM (SELECT placa FROM stg_licenciamento"
            " GROUP BY placa HAVING COUNT(*) > 1)")).scalar()
        assert duplicadas > 0


def test_us1_segundo_ciclo_sem_novidade_nao_acrescenta_nada(ambiente_pipeline):
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    executar_ciclo()
    antes = _contagens_staging(engine)

    resumo2 = executar_ciclo()

    assert _contagens_staging(engine) == antes
    for fonte, r in resumo2.items():
        assert r["situacao"] == "sem_novidade", (fonte, r)
        assert r["extraidos"] == 0, (fonte, r)


# ---------- T021/T022: aceitação US2 — qualidade (SC-002, FR-011) ----------

CONSOLIDADAS_EVENTO = ["abastecimento", "multa", "manutencao", "licenciamento"]
MOTIVOS_R7 = {
    "placa_invalida", "data_ausente", "data_invalida", "valor_invalido",
    "tipo_desconhecido", "categoria_desconhecida", "situacao_desconhecida",
    "duplicado", "veiculo_desconhecido", "fonte_indisponivel",
}


def test_us2_sc002_inconsistencias_normalizadas_ou_rejeitadas(ambiente_pipeline):
    """Ciclo completo sobre os seeds: consolidado limpo + rejeições com motivo,
    sem perda silenciosa (conservação: extraidos == consolidados + rejeitados)."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    resumo = executar_ciclo()

    # conservação por fonte no 1º ciclo — nenhuma linha some sem rastro (SC-002)
    for fonte in ["abastecimento", "multas", "manutencao", "licenciamento"]:
        r = resumo[fonte]
        assert r["extraidos"] == r["consolidados"] + r["rejeitados"], (fonte, r)

    with engine.connect() as c:
        # placas 100% canônicas — hífen, minúscula e espaço reconciliados (US2.1)
        for t in CONSOLIDADAS_EVENTO:
            assert c.execute(sql_text(
                f"SELECT COUNT(*) FROM {t} WHERE placa GLOB '*[a-z-]*'")).scalar() == 0, t

        # datas em tipo DATE (ISO) e decimais numéricos (US2.2/US2.3)
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM abastecimento WHERE data NOT GLOB"
            " '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")).scalar() == 0
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM abastecimento WHERE litros LIKE '%,%'")).scalar() == 0

        # vocabulários dentro dos CHECKs do banco (US2.4)
        tipos = {r[0] for r in c.execute(sql_text("SELECT DISTINCT tipo FROM manutencao"))}
        cats = {r[0] for r in c.execute(sql_text("SELECT DISTINCT categoria FROM manutencao"))}
        assert tipos <= {"troca_oleo", "filtros", "pneus", "revisao_geral"}, tipos
        assert cats <= {"preventiva", "corretiva"}, cats

        # licenciamento deduplicado por placa (vencimento mais recente vence — US2.5)
        n_stg = c.execute(sql_text("SELECT COUNT(*) FROM stg_licenciamento")).scalar()
        n_con = c.execute(sql_text("SELECT COUNT(*) FROM licenciamento")).scalar()
        n_dup = c.execute(sql_text(
            "SELECT COUNT(*) FROM log_qualidade"
            " WHERE fonte='licenciamento' AND motivo_rejeicao='duplicado'")).scalar()
        assert n_con < n_stg and n_stg == n_con + n_dup, (n_stg, n_con, n_dup)

        # todos os motivos pertencem ao vocabulário fechado (R7); bruto preservado
        motivos = {r[0] for r in c.execute(sql_text("SELECT DISTINCT motivo_rejeicao FROM log_qualidade"))}
        assert motivos <= MOTIVOS_R7, motivos
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM log_qualidade"
            " WHERE registro_bruto IS NULL OR registro_bruto = ''")).scalar() == 0

        # km do hodômetro persistido na consolidada (ADR-002)
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM abastecimento WHERE km_hodometro IS NOT NULL")).scalar() > 0


def test_us2_lote_parcialmente_corrompido_nunca_tudo_ou_nada(ambiente_pipeline):
    """Edge case: linhas válidas entram, inválidas vão ao log com o motivo exato —
    inclui placa canônica sem cadastro (veiculo_desconhecido, R4)."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    executar_ciclo()

    with engine.connect() as c:
        placa_boa = c.execute(sql_text("SELECT placa FROM veiculo LIMIT 1")).scalar()

    from pipeline.config import inbox_dir
    (inbox_dir() / "lote_sujo.csv").write_text(
        "placa,data,litros,valor,condutor,km\n"
        f'{placa_boa},01/07/2026,"10,0","55,00",COND-001,99999\n'   # válida
        '@@@@,01/07/2026,"10,0","55,00",COND-001,\n'                # placa_invalida
        'ZZZ9Z99,01/07/2026,"10,0","55,00",COND-001,\n'             # veiculo_desconhecido
        f'{placa_boa},31/02/2026,"10,0","55,00",COND-001,\n'        # data_invalida
        f'{placa_boa},,"10,0","55,00",COND-001,\n'                  # data_ausente
        f'{placa_boa},02/07/2026,"abc","55,00",COND-001,\n'         # valor_invalido
    )

    resumo = executar_ciclo()

    assert resumo["abastecimento"]["consolidados"] == 1, resumo["abastecimento"]
    assert resumo["abastecimento"]["rejeitados"] == 5, resumo["abastecimento"]
    with engine.connect() as c:
        motivos = {r[0]: r[1] for r in c.execute(sql_text(
            "SELECT motivo_rejeicao, COUNT(*) FROM log_qualidade"
            " WHERE fonte='abastecimento' GROUP BY 1"))}
        assert motivos == {"placa_invalida": 1, "veiculo_desconhecido": 1,
                           "data_invalida": 1, "data_ausente": 1, "valor_invalido": 1}, motivos
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM abastecimento WHERE placa = :p AND data = '2026-07-01'"),
            {"p": placa_boa}).scalar() == 1


def test_us2_cnh_nunca_chega_a_consolidada(ambiente_pipeline):
    """FR-011 (LGPD): a cnh sintética existe no staging (trilha bruta) mas nenhum
    valor dela aparece em qualquer consolidada — o descarte é estrutural."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    executar_ciclo()

    with engine.connect() as c:
        cnhs = {r[0] for r in c.execute(sql_text(
            "SELECT DISTINCT cnh FROM stg_multas WHERE cnh IS NOT NULL"))}
        assert cnhs, "staging deveria reter a cnh bruta (trilha de auditoria)"
        for t in ["veiculo"] + CONSOLIDADAS_EVENTO:
            for row in c.execute(sql_text(f"SELECT * FROM {t}")):
                assert not (set(map(str, row)) & cnhs), f"cnh vazou em {t}"


# ---------- T024/T025: aceitação US3 — carga idempotente e km_atual (SC-001, R10) ----------

TODAS_AS_TABELAS = STAGING + ["veiculo"] + CONSOLIDADAS_EVENTO + ["log_qualidade"]


def _contagens_totais(engine) -> dict[str, int]:
    with engine.connect() as c:
        return {t: c.execute(sql_text(f"SELECT COUNT(*) FROM {t}")).scalar()
                for t in TODAS_AS_TABELAS}


def _veiculo_demo_km() -> dict:
    """Veículo A da demo (gatilho por km) e o km do CSV de gatilho — dos seeds,
    sem valores mágicos no teste."""
    veiculos = json.loads((RAIZ / "data" / "seeds" / "veiculos.json").read_text())
    demo = next(v for v in veiculos if v.get("demo_gatilho") and v.get("demo_gatilho_tipo") == "km")
    linha = (RAIZ / "data" / "seeds" / "gatilho_demo_abastecimento.csv").read_text().strip().splitlines()[1]
    return {"placa": demo["placa"], "km_baseline": demo["km_atual"],
            "km_gatilho": int(linha.rsplit(",", 1)[1])}


def test_us3_sc001_dupla_execucao_estado_identico(ambiente_pipeline):
    """SC-001: 2ª execução sem dados novos → contagens idênticas em consolidadas,
    staging E log_qualidade; resumo inteiro sem_novidade/0."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    executar_ciclo()
    antes = _contagens_totais(engine)

    resumo2 = executar_ciclo()

    assert _contagens_totais(engine) == antes
    for fonte, r in resumo2.items():
        assert r == {"situacao": "sem_novidade", "extraidos": 0,
                     "consolidados": 0, "rejeitados": 0}, (fonte, r)


def test_us3_reprocessar_lote_antigo_e_noop(ambiente_pipeline):
    """Edge case "staging crescendo": re-transformar e re-carregar um lote antigo do
    staging não reintroduz duplicatas — as chaves UNIQUE tornam o upsert no-op (R2/R3)."""
    from db.models import StgAbastecimento
    from pipeline.load.upsert import upsert_abastecimento
    from pipeline.run_etl import executar_ciclo
    from pipeline.transform.qualidade import transformar_abastecimento

    engine = ambiente_pipeline
    executar_ciclo()
    antes = _contagens_totais(engine)

    with engine.connect() as c:
        lote_antigo = c.execute(func.min(StgAbastecimento.carga_em).select()).scalar()
    validos, _rejeicoes = transformar_abastecimento(engine, lote_antigo)

    assert validos, "lote antigo deveria re-produzir candidatos"
    assert upsert_abastecimento(engine, validos) == 0  # nada novo entra
    assert _contagens_totais(engine) == antes


def test_us3_momento_da_demo_gatilho_eleva_km_atual(ambiente_pipeline):
    """FR-010/R10: o histórico não rebaixa km_atual (baseline do cadastro preservado);
    o CSV de gatilho da demo eleva km_atual; renomear o mesmo conteúdo é no-op (R1)."""
    from pipeline.config import inbox_dir
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    demo = _veiculo_demo_km()
    executar_ciclo()

    with engine.connect() as c:
        km1 = c.execute(sql_text("SELECT km_atual FROM veiculo WHERE placa = :p"),
                        {"p": demo["placa"]}).scalar()
        max_csv = c.execute(sql_text(
            "SELECT MAX(km_hodometro) FROM abastecimento WHERE placa = :p"),
            {"p": demo["placa"]}).scalar()
    # monotonicidade: o CSV histórico (max < baseline) NÃO rebaixa o km_atual
    assert max_csv <= demo["km_baseline"], "premissa dos seeds mudou — revisar teste"
    assert km1 == demo["km_baseline"]

    # gesto da demo: depositar o gatilho → só ele processa, km_atual sobe (R10)
    shutil.copy(RAIZ / "data" / "seeds" / "gatilho_demo_abastecimento.csv",
                inbox_dir() / "gatilho_demo_abastecimento.csv")
    resumo = executar_ciclo()

    assert resumo["abastecimento"]["situacao"] == "ok"
    assert resumo["abastecimento"]["extraidos"] == 1
    assert resumo["abastecimento"]["consolidados"] == 1
    for fonte in ["cadastro", "multas", "manutencao", "licenciamento"]:
        assert resumo[fonte]["situacao"] == "sem_novidade", fonte
    with engine.connect() as c:
        km2 = c.execute(sql_text("SELECT km_atual FROM veiculo WHERE placa = :p"),
                        {"p": demo["placa"]}).scalar()
    assert km2 == demo["km_gatilho"] and km2 > km1

    # mesmo conteúdo com outro nome → hash igual, estado inalterado (R1)
    shutil.copy(RAIZ / "data" / "seeds" / "gatilho_demo_abastecimento.csv",
                inbox_dir() / "gatilho_renomeado.csv")
    resumo3 = executar_ciclo()
    assert resumo3["abastecimento"]["situacao"] == "sem_novidade"
    with engine.connect() as c:
        km3 = c.execute(sql_text("SELECT km_atual FROM veiculo WHERE placa = :p"),
                        {"p": demo["placa"]}).scalar()
    assert km3 == km2


# ---------- T027: aceitação US4 — resiliência por fonte (SC-005, R8) ----------


def test_us4_sc005_fonte_fora_nao_derruba_ciclo_e_recupera(ambiente_pipeline, monkeypatch):
    """API de multas fora do ar: as outras 3 fontes consolidam 100% no mesmo ciclo,
    a falha fica em log_qualidade (fonte_indisponivel) — e quando a API volta, o
    ciclo seguinte extrai normalmente, sem intervenção."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline

    def _get_porta_morta(url, timeout=None):
        raise httpx.ConnectError("porta morta")

    monkeypatch.setattr(httpx, "get", _get_porta_morta)
    resumo = executar_ciclo()

    # fonte isolada: resumo do contrato, sem exceção propagada (R8)
    assert resumo["multas"] == {"situacao": "indisponivel", "extraidos": 0,
                                "consolidados": 0, "rejeitados": 1}
    # as 3 fontes disponíveis processam 100% dos seus dados (SC-005)
    for fonte in ["abastecimento", "manutencao", "licenciamento"]:
        r = resumo[fonte]
        assert r["situacao"] == "ok", (fonte, r)
        assert r["extraidos"] > 0 and r["extraidos"] == r["consolidados"] + r["rejeitados"], (fonte, r)

    with engine.connect() as c:
        # extração de multas nem chegou ao staging; diagnóstico no log com o erro
        assert c.execute(sql_text("SELECT COUNT(*) FROM stg_multas")).scalar() == 0
        fonte, registro = c.execute(sql_text(
            "SELECT fonte, registro_bruto FROM log_qualidade"
            " WHERE motivo_rejeicao = 'fonte_indisponivel'")).one()
        assert fonte == "multas" and "ConnectError" in registro

    # auto-recuperação: a API volta → próximo ciclo extrai sem intervenção
    payload = (RAIZ / "fake_api" / "multas.json").read_bytes()
    monkeypatch.setattr(httpx, "get", lambda url, timeout=None: httpx.Response(
        200, content=payload, request=httpx.Request("GET", url)))
    resumo2 = executar_ciclo()

    assert resumo2["multas"]["situacao"] == "ok"
    assert resumo2["multas"]["extraidos"] == len(json.loads(payload))
    for fonte in ["cadastro", "abastecimento", "manutencao", "licenciamento"]:
        assert resumo2[fonte]["situacao"] == "sem_novidade", fonte


# ---------- Follow-up ciclo 1 SDD: BUG-1 + e2e dos motivos defense-in-depth ----------


def _placas_validas(n: int) -> list[str]:
    """Primeiras n placas do cadastro canônico (garante que os testes de motivo
    não caiam em veiculo_desconhecido)."""
    veiculos = json.loads((RAIZ / "data" / "seeds" / "veiculos.json").read_text())
    return [v["placa"] for v in veiculos[:n]]


def _motivos(engine, fonte: str) -> dict[str, int]:
    with engine.connect() as c:
        return {r[0]: r[1] for r in c.execute(sql_text(
            "SELECT motivo_rejeicao, COUNT(*) FROM log_qualidade"
            " WHERE fonte = :f GROUP BY 1"), {"f": fonte})}


def test_bug1_multas_payload_novo_mas_vazio_e_ok_nao_indisponivel(ambiente_pipeline, monkeypatch):
    """BUG-1 (revisão SDD ciclo 1): um payload de multas NOVO (hash inédito) mas
    VAZIO ([]) é fonte DISPONÍVEL — situacao=ok, extraidos=0 — NUNCA fonte_indisponivel.
    Sem a guarda `if linhas:`, o insert vazio virava INSERT ... DEFAULT VALUES →
    IntegrityError → marcado espúrio como indisponível."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    monkeypatch.setattr(httpx, "get", lambda url, timeout=None: httpx.Response(
        200, content=b"[]", request=httpx.Request("GET", url)))

    resumo = executar_ciclo()

    assert resumo["multas"] == {"situacao": "ok", "extraidos": 0,
                                "consolidados": 0, "rejeitados": 0}, resumo["multas"]
    with engine.connect() as c:
        assert c.execute(sql_text("SELECT COUNT(*) FROM stg_multas")).scalar() == 0
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM log_qualidade"
            " WHERE fonte='multas' AND motivo_rejeicao='fonte_indisponivel'")).scalar() == 0


def test_e2e_rejeicao_manutencao_motivos_defense_in_depth(ambiente_pipeline, monkeypatch, tmp_path):
    """e2e: um XLSX de manutenção com um defeito por linha conduz cada motivo
    (tipo/categoria_desconhecida, data_invalida, valor_invalido) ao log_qualidade —
    a linha válida consolida (nunca tudo-ou-nada)."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    (p,) = _placas_validas(1)
    xlsx = tmp_path / "manutencao_suja.xlsx"
    pd.DataFrame(
        [
            {"placa": p, "data": "2026-03-01", "tipo": "troca de oleo", "categoria": "preventiva", "km_no_momento": "1000", "valor": "100.00"},  # válida
            {"placa": p, "data": "2026-03-02", "tipo": "lavagem",       "categoria": "preventiva", "km_no_momento": "1000", "valor": "100.00"},  # tipo_desconhecido
            {"placa": p, "data": "2026-03-03", "tipo": "filtros",       "categoria": "xyz",        "km_no_momento": "1000", "valor": "100.00"},  # categoria_desconhecida
            {"placa": p, "data": "31/02/2026", "tipo": "pneus",         "categoria": "corretiva",  "km_no_momento": "1000", "valor": "100.00"},  # data_invalida
            {"placa": p, "data": "2026-03-04", "tipo": "pneus",         "categoria": "corretiva",  "km_no_momento": "abc",  "valor": "100.00"},  # valor_invalido (km)
        ]
    ).to_excel(xlsx, sheet_name="Oficina Central", index=False)
    monkeypatch.setenv("PIPELINE_XLSX_MANUTENCAO", str(xlsx))

    executar_ciclo()

    assert _motivos(engine, "manutencao") == {
        "tipo_desconhecido": 1, "categoria_desconhecida": 1,
        "data_invalida": 1, "valor_invalido": 1,
    }
    with engine.connect() as c:
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM manutencao WHERE placa = :p AND data = '2026-03-01'"),
            {"p": p}).scalar() == 1


def test_e2e_rejeicao_multas_motivos_defense_in_depth(ambiente_pipeline, monkeypatch):
    """e2e: um payload de multas com um defeito por item conduz situacao_desconhecida,
    valor_invalido e data_invalida ao log_qualidade; o item válido consolida."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    (p,) = _placas_validas(1)
    payload = [
        {"placa": p.lower(), "data": "2026-05-01", "valor": 100.0, "condutor": "COND-001", "situacao": "pendente", "gravidade": "leve", "cnh": "123", "codigo_infracao": "1"},   # válida
        {"placa": p.lower(), "data": "2026-05-02", "valor": 100.0, "condutor": "COND-001", "situacao": "cancelada"},   # situacao_desconhecida
        {"placa": p.lower(), "data": "2026-05-03", "valor": "abc",  "condutor": "COND-001", "situacao": "paga"},        # valor_invalido
        {"placa": p.lower(), "data": "31/02/2026", "valor": 100.0, "condutor": "COND-001", "situacao": "paga"},        # data_invalida
    ]
    corpo = json.dumps(payload).encode()
    monkeypatch.setattr(httpx, "get", lambda url, timeout=None: httpx.Response(
        200, content=corpo, request=httpx.Request("GET", url)))

    executar_ciclo()

    assert _motivos(engine, "multas") == {
        "situacao_desconhecida": 1, "valor_invalido": 1, "data_invalida": 1,
    }
    with engine.connect() as c:
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM multa WHERE placa = :p AND data = '2026-05-01'"),
            {"p": p}).scalar() == 1


def test_e2e_rejeicao_licenciamento_motivos_defense_in_depth(ambiente_pipeline, monkeypatch, tmp_path):
    """e2e: um SQLite legado de licenciamento com placas distintas (dedup é por placa)
    conduz situacao_desconhecida e data_invalida ao log_qualidade; a placa válida consolida."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    p_ok, p_sit, p_data = _placas_validas(3)
    legado = tmp_path / "licenciamento_sujo.sqlite"
    con = sqlite3.connect(legado)
    con.execute("CREATE TABLE licenciamento (placa TEXT, vencimento TEXT, situacao TEXT)")
    con.executemany("INSERT INTO licenciamento VALUES (?,?,?)", [
        (p_ok,   "2026-12-01", "em_dia"),     # válida
        (p_sit,  "2026-12-01", "suspenso"),   # situacao_desconhecida
        (p_data, "31/02/2026", "vencido"),    # data_invalida
    ])
    con.commit(); con.close()
    monkeypatch.setenv("PIPELINE_SQLITE_LICENCIAMENTO", str(legado))

    executar_ciclo()

    assert _motivos(engine, "licenciamento") == {
        "situacao_desconhecida": 1, "data_invalida": 1,
    }
    with engine.connect() as c:
        assert c.execute(sql_text(
            "SELECT COUNT(*) FROM licenciamento WHERE placa = :p"), {"p": p_ok}).scalar() == 1


# ---------- ADR-005: coalesce-preserva-não-nulo no upsert de dimensões (Devin-B) ----------


def test_adr005_licenciamento_null_entrante_nao_zera_persistido(ambiente_pipeline, monkeypatch, tmp_path):
    """ADR-005/Devin-B: um lote de licenciamento com vencimento/situacao NULL NÃO
    zera o valor já consolidado — `COALESCE(excluded.col, tabela.col)`."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    (p,) = _placas_validas(1)
    legado = tmp_path / "lic.sqlite"

    def _escrever(rows):
        legado.unlink(missing_ok=True)
        con = sqlite3.connect(legado)
        con.execute("CREATE TABLE licenciamento (placa TEXT, vencimento TEXT, situacao TEXT)")
        con.executemany("INSERT INTO licenciamento VALUES (?,?,?)", rows)
        con.commit(); con.close()

    monkeypatch.setenv("PIPELINE_SQLITE_LICENCIAMENTO", str(legado))
    _escrever([(p, "2026-12-01", "em_dia")])
    executar_ciclo()
    with engine.connect() as c:
        v0, s0 = c.execute(sql_text(
            "SELECT vencimento, situacao FROM licenciamento WHERE placa = :p"), {"p": p}).one()
    assert str(v0) == "2026-12-01" and s0 == "em_dia"

    # lote novo (hash novo), mesma placa, campos anuláveis vazios → deve PRESERVAR
    _escrever([(p, "", "")])
    resumo = executar_ciclo()
    assert resumo["licenciamento"]["situacao"] == "ok"  # re-extraído (conteúdo mudou)
    with engine.connect() as c:
        v1, s1 = c.execute(sql_text(
            "SELECT vencimento, situacao FROM licenciamento WHERE placa = :p"), {"p": p}).one()
    assert str(v1) == "2026-12-01", "vencimento foi zerado — COALESCE falhou"
    assert s1 == "em_dia", "situacao foi zerada — COALESCE falhou"


def test_adr005_cadastro_null_entrante_nao_zera_persistido(ambiente_pipeline, monkeypatch, tmp_path):
    """ADR-005: um cadastro sem modelo/ano/secretaria NÃO zera os valores já
    persistidos do veículo (coalesce-preserva); km_atual permanece intocado (monotonic-exclude)."""
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_pipeline
    executar_ciclo()  # cadastro default: 40 veículos com modelo/ano/secretaria
    (p,) = _placas_validas(1)
    with engine.connect() as c:
        modelo0, ano0, sec0, km0 = c.execute(sql_text(
            "SELECT modelo, ano, secretaria, km_atual FROM veiculo WHERE placa = :p"), {"p": p}).one()
    assert modelo0 and ano0 and sec0  # baseline não-nulo

    # cadastro novo (hash novo) com a placa mas descritivos ausentes
    cad = tmp_path / "cadastro_min.json"
    cad.write_text(json.dumps([{"placa": p, "tipo_veiculo": "leve"}]))
    monkeypatch.setenv("PIPELINE_CADASTRO_VEICULOS", str(cad))
    resumo = executar_ciclo()
    assert resumo["cadastro"]["situacao"] == "ok"

    with engine.connect() as c:
        modelo1, ano1, sec1, km1 = c.execute(sql_text(
            "SELECT modelo, ano, secretaria, km_atual FROM veiculo WHERE placa = :p"), {"p": p}).one()
    assert (modelo1, ano1, sec1) == (modelo0, ano0, sec0), "descritivo zerado — COALESCE falhou"
    assert km1 == km0, "km_atual alterado pelo cadastro — monotonic-exclude falhou"
