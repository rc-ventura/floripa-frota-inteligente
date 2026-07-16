"""Testes de aceitação da spec 002 — Modelo de Dados e Banco Consolidado.

Cobre: criação do zero (FR-001..003), placa canônica dual (ADR-001), índice único
parcial de alerta ativo (research R6), seed da LIMIAR_CONFIG (FR-004), edição de
limiar em runtime (SC-002), idempotência (SC-004) e introspecção LGPD (SC-003).
"""

import json
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

import db.config
import db.init_db
import db.seed_limiares
from db.models import (
    Alerta,
    LimiarConfig,
    Manutencao,
    Multa,
    Veiculo,
)

RAIZ = Path(__file__).resolve().parents[1]
SEMENTE = RAIZ / "data" / "seeds" / "limiares_semente.json"

CONSOLIDADAS = ["veiculo", "abastecimento", "manutencao", "multa", "licenciamento"]
STAGING = ["stg_abastecimento", "stg_multas", "stg_manutencao", "stg_licenciamento"]
TABELAS_ESPERADAS = set(CONSOLIDADAS) | set(STAGING) | {
    "limiar_config",
    "alerta",
    "log_qualidade",
}


# ---------- Fixtures base (T003) ----------


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Banco SQLite limpo em tmp_path, inicializado pelo comando oficial."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/frota.db")
    db.config.reset_engine()
    db.init_db.main()
    yield db.config.get_engine()
    db.config.reset_engine()


@pytest.fixture
def sessao(banco):
    """Sessão SQLAlchemy para asserções sobre o banco inicializado."""
    with db.config.get_session(banco) as s:
        yield s


def _veiculo(placa="ABC1234", tipo="leve"):
    return Veiculo(placa=placa, tipo_veiculo=tipo, fonte_origem="teste")


# ---------- US1 — Esquema completo criado do zero ----------


def test_criacao_do_zero(banco):
    """T007: 1 execução cria as 12 tabelas + alembic_version com colunas-chave."""
    insp = inspect(banco)
    tabelas = set(insp.get_table_names())

    assert TABELAS_ESPERADAS <= tabelas, f"faltam: {TABELAS_ESPERADAS - tabelas}"
    assert "alembic_version" in tabelas, "criação deve ser versionada (Alembic)"
    assert len(TABELAS_ESPERADAS) == 12

    colunas = {t: {c["name"] for c in insp.get_columns(t)} for t in tabelas}
    assert "km_hodometro" in colunas["abastecimento"]  # ADR-002
    assert "categoria" in colunas["manutencao"]  # ADR-003
    assert "fonte_origem" in colunas["veiculo"]  # research R8
    assert "detalhe" in colunas["alerta"]  # spec 004 FR-005
    assert "aba_origem" in colunas["stg_manutencao"]
    assert {"fonte", "registro_bruto", "motivo_rejeicao", "carga_em"} <= colunas[
        "log_qualidade"
    ]


def test_placa_e_relacionamentos(sessao):
    """T008: placa canônica dual aceita; inválida rejeitada; FKs e CHECKs ativos."""
    # dois formatos vigentes (ADR-001)
    sessao.add(_veiculo("ABC1234"))  # antigo
    sessao.add(_veiculo("ABC1D23"))  # Mercosul
    sessao.commit()

    # fora do canônico → ValueError do @validates, antes do INSERT
    for invalida in ("AB1234", "abc1234", "ABC-1234", "ABC12345"):
        with pytest.raises(ValueError):
            _veiculo(invalida)

    # evento com placa inexistente → falha de FK
    sessao.add(
        Manutencao(
            placa="ZZZ9999",
            data=date(2026, 7, 1),
            tipo="troca_oleo",
            categoria="preventiva",
            fonte_origem="teste",
        )
    )
    with pytest.raises(IntegrityError):
        sessao.commit()
    sessao.rollback()

    # CHECKs de vocabulário
    invalidos = [
        Veiculo(placa="DEF1234", tipo_veiculo="moto", fonte_origem="teste"),
        Manutencao(
            placa="ABC1234",
            data=date(2026, 7, 1),
            tipo="lavagem",
            categoria="preventiva",
            fonte_origem="teste",
        ),
        Manutencao(
            placa="ABC1234",
            data=date(2026, 7, 1),
            tipo="troca_oleo",
            categoria="urgente",
            fonte_origem="teste",
        ),
        Multa(
            placa="ABC1234",
            data=date(2026, 7, 1),
            valor=195,
            situacao="atrasada",
            fonte_origem="teste",
        ),
    ]
    for obj in invalidos:
        sessao.add(obj)
        with pytest.raises(IntegrityError):
            sessao.commit()
        sessao.rollback()


def test_alerta_ativo_unico(sessao):
    """T009: índice parcial ux_alerta_ativo — 1 alerta ativo por (placa, gatilho, limiar)."""
    sessao.add(_veiculo("ABC1234"))
    sessao.commit()
    limiar_id = sessao.execute(select(LimiarConfig.id)).scalars().first()
    assert limiar_id is not None, "seed deve ter populado limiar_config"

    def alerta(gatilho="km", limiar=limiar_id):
        return Alerta(
            placa="ABC1234",
            limiar_id=limiar,
            tipo_gatilho=gatilho,
            gerado_em=datetime(2026, 7, 16, 12, 0),
        )

    primeiro = alerta()
    sessao.add(primeiro)
    sessao.commit()
    assert primeiro.situacao == "ativo"  # default

    # 2º ativo idêntico → rejeitado pelo banco
    sessao.add(alerta())
    with pytest.raises(IntegrityError):
        sessao.commit()
    sessao.rollback()

    # resolver o 1º libera nova ocorrência (recorrência não bloqueada)
    primeiro = sessao.get(Alerta, primeiro.id)
    primeiro.situacao = "resolvido"
    sessao.commit()
    sessao.add(alerta())
    sessao.commit()

    # dados_insuficientes (limiar_id NULL) segue a mesma regra via coalesce
    sessao.add(alerta(gatilho="dados_insuficientes", limiar=None))
    sessao.commit()
    sessao.add(alerta(gatilho="dados_insuficientes", limiar=None))
    with pytest.raises(IntegrityError):
        sessao.commit()
    sessao.rollback()


# ---------- US2 — Limiares como dados ----------


def test_seed_limiares(banco, sessao):
    """T016: limiar_config espelha o JSON; re-init idempotente; par ausente = vazio."""
    esperado = {
        (l["tipo_veiculo"], l["tipo_manutencao"]): l
        for l in json.loads(SEMENTE.read_text())
    }
    assert len(esperado) == 9

    def linhas():
        return {
            (l.tipo_veiculo, l.tipo_manutencao): l
            for l in sessao.execute(select(LimiarConfig)).scalars()
        }

    banco_agora = linhas()
    assert set(banco_agora) == set(esperado)
    for chave, semente in esperado.items():
        for campo, valor in semente.items():
            assert getattr(banco_agora[chave], campo) == valor, (chave, campo)

    # re-init não duplica, não altera e não perde dados (SC-004)
    sessao.add(_veiculo("SOB1234"))
    sessao.commit()
    db.init_db.main()
    sessao.expire_all()
    assert set(linhas()) == set(esperado)
    assert sessao.get(Veiculo, "SOB1234") is not None, "re-init perdeu dados"

    # par inexistente → vazio (ausência detectável, sem default silencioso)
    assert ("ambulancia", "pneus") not in esperado  # premissa do edge case
    faltante = sessao.execute(
        select(LimiarConfig).where(
            LimiarConfig.tipo_veiculo == "ambulancia",
            LimiarConfig.tipo_manutencao == "pneus",
        )
    ).scalar_one_or_none()
    assert faltante is None


def test_limiar_runtime(banco, sessao):
    """T017: edição em runtime visível sem restart; seed não sobrescreve; --sobrescrever sim."""
    filtro = (
        LimiarConfig.tipo_veiculo == "leve",
        LimiarConfig.tipo_manutencao == "troca_oleo",
    )
    original = sessao.execute(select(LimiarConfig).where(*filtro)).scalar_one()
    valor_json = original.limite_km

    original.limite_km = 4000
    sessao.commit()

    # outra sessão vê o novo valor sem reinicialização (proxy do SC-002)
    with db.config.get_session(banco) as outra:
        assert (
            outra.execute(select(LimiarConfig).where(*filtro)).scalar_one().limite_km
            == 4000
        )

    # re-seed padrão NÃO sobrescreve a edição ao vivo
    db.seed_limiares.seed(banco)
    sessao.expire_all()
    assert sessao.execute(select(LimiarConfig).where(*filtro)).scalar_one().limite_km == 4000

    # recalibração deliberada: --sobrescrever adota os valores do JSON
    db.seed_limiares.seed(banco, sobrescrever=True)
    sessao.expire_all()
    assert (
        sessao.execute(select(LimiarConfig).where(*filtro)).scalar_one().limite_km
        == valor_json
    )


# ---------- US3 — Rastreabilidade e LGPD ----------


def test_rastreabilidade_lgpd(banco):
    """T020: fonte_origem/carga_em estruturais; zero coluna de identidade real; zero de-para."""
    insp = inspect(banco)
    tabelas = insp.get_table_names()
    colunas = {t: {c["name"] for c in insp.get_columns(t)} for t in tabelas}

    for t in CONSOLIDADAS:
        assert "fonte_origem" in colunas[t], f"{t} sem fonte_origem (constitution II)"
    for t in STAGING:
        assert {"carga_em", "fonte_origem"} <= colunas[t], f"{t} sem carimbo de carga"

    proibidas = {"nome", "cpf", "matricula", "cnh"}
    for t in CONSOLIDADAS + ["alerta", "limiar_config"]:
        assert not (colunas[t] & proibidas), f"{t} tem coluna de identidade real"

    assert not [t for t in tabelas if "condutor" in t], "existe tabela de-para de condutor"
