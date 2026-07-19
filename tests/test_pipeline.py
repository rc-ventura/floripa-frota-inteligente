"""Testes da spec 003 — Pipeline ETL de Integração das Fontes.

T010: testes unitários dos normalizadores (research R5/R6) — placa dual (ADR-001),
datas nos 3 formatos (incluindo serial Excel), decimais com vírgula e as grafias de
tipo/categoria catalogadas em data/seeds/INCONSISTENCIAS.md.

T016: aceitação da US1 — 1 ciclo popula os 4 stagings com bruto intacto + carimbo
de carga + fonte_origem com hash (R1); 2º ciclo sem novidade não acrescenta nada.

As demais fases (US2–US4) acrescentam seus testes de aceitação aqui (T021, T022,
T024, T025, T027).
"""

import re
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text as sql_text

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
def ambiente_us1(tmp_path, monkeypatch):
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


def test_us1_ciclo_popula_staging_bruto_com_rastreabilidade(ambiente_us1):
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_us1
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


def test_us1_segundo_ciclo_sem_novidade_nao_acrescenta_nada(ambiente_us1):
    from pipeline.run_etl import executar_ciclo

    engine = ambiente_us1
    executar_ciclo()
    antes = _contagens_staging(engine)

    resumo2 = executar_ciclo()

    assert _contagens_staging(engine) == antes
    for fonte, r in resumo2.items():
        assert r["situacao"] == "sem_novidade", (fonte, r)
        assert r["extraidos"] == 0, (fonte, r)
