"""Testes da spec 003 — Pipeline ETL de Integração das Fontes.

T010: testes unitários dos normalizadores (research R5/R6) — placa dual (ADR-001),
datas nos 3 formatos (incluindo serial Excel), decimais com vírgula e as grafias de
tipo/categoria catalogadas em data/seeds/INCONSISTENCIAS.md.

As demais fases (US1–US4) acrescentam seus testes de aceitação aqui (T016, T021,
T022, T024, T025, T027).
"""

from datetime import date
from decimal import Decimal

import pytest

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
