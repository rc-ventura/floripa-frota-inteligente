"""Testes de aceitação da spec 001 — Fontes de Dados Simuladas.

Cobrem os quickstart Cenários 1–8: artefatos (US1), inconsistências (US2),
cenário determinístico da demo (US3), LGPD (US4) e coerência física (SC-005/SC-006).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
ANCORA = date(2026, 7, 15)

REGEX_CANONICO = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")   # antigo + Mercosul (ADR-001)
REGEX_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")
FAIXA_KM_L = {"leve": (8, 14), "ambulancia": (6, 10), "caminhao": (2, 5)}  # SC-005
VALORES_CTB = {88.38, 130.16, 195.23, 293.47, 586.94, 880.41}  # 4 gravidades + gravíssima ×2/×3
CAL_DETRAN_MES = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 0: 12}
MARCO_KM = 10000

sys.path.insert(0, str(RAIZ))            # fake_api.main
sys.path.insert(0, str(RAIZ / "data"))   # gerador_dados (validador de CNH)


# ---------------------------------------------------------------------------
# Helpers (espelham as normalizações que a spec 003 fará no pipeline)
# ---------------------------------------------------------------------------

def normalizar_placa(p: str) -> str:
    return str(p).upper().replace("-", "").replace(" ", "")


def parse_data(v) -> date:
    """Parsing tolerante: dd/mm/aaaa, aaaa-mm-dd ou serial Excel (INTEGER)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v).strip()
    if s.isdigit():
        return date(1899, 12, 30) + timedelta(days=int(s))
    if "/" in s:
        d, m, a = s.split("/")
        return date(int(a), int(m), int(d))
    return date.fromisoformat(s[:10])


def norm_tipo(t: str) -> str:
    s = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    if "filtro" in s:
        return "filtros"
    if "oleo" in s:
        return "troca_oleo"
    if "pneu" in s:
        return "pneus"
    if "revis" in s:
        return "revisao_geral"
    return "?"


def norm_categoria(c: str) -> str:
    return "preventiva" if str(c).strip().lower().startswith("p") else "corretiva"


# ---------------------------------------------------------------------------
# Fixtures (T003): geração única por sessão + leitores por fonte
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def geracao() -> Path:
    subprocess.run(
        [sys.executable, str(RAIZ / "data" / "gerador_dados.py"),
         "--data-ancora", ANCORA.isoformat()],
        check=True, cwd=RAIZ,
    )
    return RAIZ


@pytest.fixture(scope="session")
def veiculos(geracao):
    return json.loads((geracao / "data/seeds/veiculos.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def csv_abastecimento(geracao):
    df = pd.read_csv(geracao / "data/seeds/abastecimento.csv", dtype=str)
    df["km"] = df["km"].astype(int)
    return df


@pytest.fixture(scope="session")
def xlsx_manutencao(geracao):
    abas = pd.read_excel(geracao / "data/seeds/manutencao.xlsx", sheet_name=None)
    for nome, df in abas.items():
        df["_aba"] = nome
    return pd.concat(abas.values(), ignore_index=True)


@pytest.fixture(scope="session")
def multas(geracao):
    return json.loads((geracao / "fake_api/multas.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def licenciamento(geracao):
    con = sqlite3.connect(geracao / "data/seeds/licenciamento.sqlite")
    linhas = con.execute("SELECT placa, vencimento, situacao FROM licenciamento").fetchall()
    con.close()
    return linhas


# ---------------------------------------------------------------------------
# US1 — Quatro fontes heterogêneas (T009–T011)
# ---------------------------------------------------------------------------

def test_artefatos_existem(geracao):
    esperados = [
        "data/seeds/veiculos.json", "data/seeds/limiares_semente.json",
        "data/seeds/abastecimento.csv", "data/seeds/manutencao.xlsx",
        "data/seeds/licenciamento.sqlite", "data/seeds/gatilho_demo_abastecimento.csv",
        "data/seeds/INCONSISTENCIAS.md", "fake_api/multas.json",
    ]
    for rel in esperados:
        assert (geracao / rel).exists(), f"artefato ausente: {rel}"
    assert len(pd.ExcelFile(geracao / "data/seeds/manutencao.xlsx").sheet_names) == 3
    limiares = json.loads((geracao / "data/seeds/limiares_semente.json").read_text(encoding="utf-8"))
    assert len(limiares) == 9


def test_mesmo_conjunto_veiculos(veiculos, csv_abastecimento, xlsx_manutencao, multas, licenciamento):
    cadastro = {v["placa"] for v in veiculos}
    assert len(cadastro) == 40
    assert {normalizar_placa(p) for p in csv_abastecimento["placa"]} == cadastro
    assert {normalizar_placa(p) for p in xlsx_manutencao["placa"]} == cadastro
    assert {normalizar_placa(p) for p, *_ in licenciamento} == cadastro
    assert {normalizar_placa(m["placa"]) for m in multas} <= cadastro


def test_endpoint_multas(geracao, multas):
    from fastapi.testclient import TestClient

    import fake_api.main as api

    api._cache = None  # garante releitura do arquivo recém-gerado
    client = TestClient(api.app)

    resposta = client.get("/multas")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == len(multas) > 0
    chaves = {"placa", "data", "gravidade", "valor", "condutor", "cnh", "situacao", "codigo_infracao"}
    assert chaves <= set(corpo[0])

    placa = corpo[0]["placa"]
    filtradas = client.get(f"/multas/{placa}")
    assert filtradas.status_code == 200
    assert len(filtradas.json()) >= 1
    assert all(m["placa"] == placa for m in filtradas.json())

    assert client.get("/health").json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# US2 — Inconsistências propositais (T019)
# ---------------------------------------------------------------------------

def test_inconsistencias(geracao, csv_abastecimento, xlsx_manutencao, multas, licenciamento):
    # CSV: hífen misturado, 2 formatos de data, vírgula decimal
    frac_hifen = csv_abastecimento["placa"].str.contains("-").mean()
    assert 0.3 < frac_hifen < 0.7
    assert csv_abastecimento["data"].str.contains("/").any()
    assert csv_abastecimento["data"].str.match(r"\d{4}-\d{2}-\d{2}").any()
    assert csv_abastecimento["litros"].str.contains(",").all()
    assert csv_abastecimento["valor"].str.contains(",").all()

    # Multas: placas 100% minúsculas, sem hífen
    assert all(m["placa"] == m["placa"].lower() and "-" not in m["placa"] for m in multas)

    # XLSX: km ausente ~15%, tipo e categoria sem padronização
    frac_na = xlsx_manutencao["km_no_momento"].isna().mean()
    assert 0.05 <= frac_na <= 0.25
    assert xlsx_manutencao["tipo"].nunique() >= 6
    assert xlsx_manutencao["categoria"].nunique() >= 3

    # SQLite: duplicatas e 3 formatos de vencimento
    placas = [p for p, *_ in licenciamento]
    assert len(placas) - len(set(placas)) >= 2
    vencs = [v for _, v, _ in licenciamento]
    assert any(isinstance(v, int) for v in vencs)
    assert any(isinstance(v, str) and "/" in v for v in vencs)
    assert any(isinstance(v, str) and "-" in v for v in vencs)

    # Documentação (FR-003)
    doc = (geracao / "data/seeds/INCONSISTENCIAS.md").read_text(encoding="utf-8")
    for trecho in ("Fonte 1", "Fonte 2", "Fonte 3", "Fonte 4"):
        assert trecho in doc


# ---------------------------------------------------------------------------
# US3 — Cenário determinístico da demo (T025–T026)
# ---------------------------------------------------------------------------

def test_cenario_demo(veiculos, xlsx_manutencao, geracao):
    a, b = veiculos[0], veiculos[1]
    assert a["demo_gatilho"] and a["demo_gatilho_tipo"] == "km"
    assert b["demo_gatilho"] and b["demo_gatilho_tipo"] == "tempo"

    man = xlsx_manutencao.copy()
    man["tipo_canonico"] = man["tipo"].map(norm_tipo)
    man["data_parsed"] = man["data"].map(parse_data)

    # Veículo A: exatamente 4400 km desde a última troca de óleo (alerta km dispara a 4500)
    oleo_a = man[(man["placa"] == a["placa"]) & (man["tipo_canonico"] == "troca_oleo")]
    ancora_a = oleo_a.loc[oleo_a["km_no_momento"].idxmax()]
    km_ultima_a = int(ancora_a["km_no_momento"])
    assert a["km_atual"] - km_ultima_a == 4400

    # Veículo B: exatamente 166 dias desde a última troca de óleo (antecedência 165 já cruzada)
    oleo_b = man[(man["placa"] == b["placa"]) & (man["tipo_canonico"] == "troca_oleo")]
    assert (ANCORA - oleo_b["data_parsed"].max()).days == 166

    # Gatilho: cruza a antecedência (4500) sem atingir o limite (5000) — antes do vencimento
    gatilho = pd.read_csv(geracao / "data/seeds/gatilho_demo_abastecimento.csv", dtype=str)
    assert len(gatilho) == 1
    assert normalizar_placa(gatilho.loc[0, "placa"]) == a["placa"]
    km_gatilho = int(gatilho.loc[0, "km"])
    assert 4500 <= km_gatilho - km_ultima_a < 5000


def test_determinismo(tmp_path_factory):
    execucoes = []
    for nome in ("run1", "run2"):
        destino = tmp_path_factory.mktemp(nome)
        subprocess.run(
            [sys.executable, str(RAIZ / "data" / "gerador_dados.py"),
             "--output", str(destino), "--data-ancora", ANCORA.isoformat()],
            check=True, cwd=RAIZ,
        )
        hashes = {
            str(arq.relative_to(destino)): hashlib.sha256(arq.read_bytes()).hexdigest()
            for arq in sorted(destino.rglob("*")) if arq.is_file()
        }
        execucoes.append(hashes)
    assert len(execucoes[0]) >= 8
    assert execucoes[0] == execucoes[1], "geração não é determinística (FR-006/SC-004)"


# ---------------------------------------------------------------------------
# US4 — Nenhum dado pessoal real (T030)
# ---------------------------------------------------------------------------

def test_lgpd_sem_dado_pessoal(csv_abastecimento, multas):
    import gerador_dados

    padrao_cond = re.compile(r"^COND-\d{3}$")
    assert all(padrao_cond.match(c) for c in csv_abastecimento["condutor"])
    for m in multas:
        assert padrao_cond.match(m["condutor"]), m["condutor"]
        cnh = m["cnh"]
        assert re.fullmatch(r"\d{11}", cnh)
        # DV recalculado ≠ DV armazenado ⇒ CNH estruturalmente inválida (R2)
        assert gerador_dados._dv_cnh(cnh[:9]) != cnh[9:], "CNH com DV válido — violação R2/SC-003"

    texto = json.dumps(multas) + csv_abastecimento.to_csv(index=False)
    assert not re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", texto), "padrão de CPF encontrado"
    assert not any(k in multas[0] for k in ("nome", "cpf", "matricula"))


def test_sem_alertas_espurios(veiculos, xlsx_manutencao, geracao):
    """Regressão do bug HIGH do ciclo 1 (sdd-final-review): nenhum veículo NÃO-demo
    pode cruzar (limite − antecedência) em km nem em dias, para nenhum tipo aplicável.

    O motor (spec 004) usa o evento mais recente com km por (placa, tipo) — se o
    injetor de km-ausente anular essa âncora, km_desde_ultima cai para um evento
    anterior e dispara alerta espúrio (invariante de data-model.md § Cadastro base).
    """
    limiares = json.loads((geracao / "data/seeds/limiares_semente.json").read_text(encoding="utf-8"))
    man = xlsx_manutencao.copy()
    man["tipo_canonico"] = man["tipo"].map(norm_tipo)
    man["data_parsed"] = man["data"].map(parse_data)

    for v in veiculos:
        if v["demo_gatilho"]:
            continue  # A e B são posicionados contra o limiar de propósito (R4)
        for lim in limiares:
            if lim["tipo_veiculo"] != v["tipo_veiculo"]:
                continue
            tipo = lim["tipo_manutencao"]
            eventos = man[(man["placa"] == v["placa"]) & (man["tipo_canonico"] == tipo)]
            assert not eventos.empty, f"{v['placa']}/{tipo}: sem evento (dados_insuficientes espúrio)"
            com_km = eventos.dropna(subset=["km_no_momento"])
            assert not com_km.empty, f"{v['placa']}/{tipo}: âncora sem km (todos anulados)"
            km_desde = v["km_atual"] - int(com_km["km_no_momento"].max())
            gatilho_km = lim["limite_km"] - lim["antecedencia_km"]
            assert km_desde < gatilho_km, \
                f"{v['placa']}/{tipo}: km_desde={km_desde} cruza o gatilho {gatilho_km}"
            dias_desde = (ANCORA - eventos["data_parsed"].max()).days
            gatilho_dias = lim["limite_dias"] - lim["antecedencia_dias"]
            assert dias_desde < gatilho_dias, \
                f"{v['placa']}/{tipo}: dias_desde={dias_desde} cruza o gatilho {gatilho_dias}"


def test_endpoint_multas_erro_500(geracao, tmp_path):
    """Caminho de erro da API (fake_api/main.py): multas.json indisponível → 500
    com detail genérico, sem vazar o caminho absoluto (achado Low do Security)."""
    from fastapi.testclient import TestClient

    import fake_api.main as api

    cache_original, caminho_original = api._cache, api.CAMINHO_MULTAS
    try:
        api._cache = None
        api.CAMINHO_MULTAS = tmp_path / "inexistente.json"
        resposta = TestClient(api.app).get("/multas")
        assert resposta.status_code == 500
        detalhe = resposta.json()["detail"]
        assert str(tmp_path) not in detalhe and "inexistente" not in detalhe, \
            f"500 vaza caminho do servidor: {detalhe}"
    finally:
        api._cache, api.CAMINHO_MULTAS = cache_original, caminho_original


# ---------------------------------------------------------------------------
# Coerência física transversal (T032 — FR-011/012/013, SC-005/SC-006)
# ---------------------------------------------------------------------------

def test_coerencia_fisica(veiculos, csv_abastecimento, xlsx_manutencao, multas, licenciamento):
    por_placa = {v["placa"]: v for v in veiculos}

    # 1. placas nos dois formatos vigentes; ~70% Mercosul (ADR-001)
    assert all(REGEX_CANONICO.match(v["placa"]) for v in veiculos)
    n_mercosul = sum(bool(REGEX_MERCOSUL.match(v["placa"])) for v in veiculos)
    assert 22 <= n_mercosul <= 34

    # 2. hodômetro monotônico por veículo, cruzando CSV × XLSX (R12)
    eventos: list[tuple[str, date, int]] = []
    for _, linha in csv_abastecimento.iterrows():
        eventos.append((normalizar_placa(linha["placa"]), parse_data(linha["data"]), int(linha["km"])))
    for _, linha in xlsx_manutencao.iterrows():
        if pd.notna(linha["km_no_momento"]):
            eventos.append((linha["placa"], parse_data(linha["data"]), int(linha["km_no_momento"])))
    for placa, veic in por_placa.items():
        kms = [k for _, k in sorted((d, k) for p, d, k in eventos if p == placa)]
        assert all(b >= a for a, b in zip(kms, kms[1:])), f"hodômetro não monotônico: {placa}"
        assert kms[-1] <= veic["km_atual"]

    # 3. consumo derivado (km rodados ÷ litros) dentro da faixa do tipo (SC-005)
    csv = csv_abastecimento.copy()
    csv["placa_norm"] = csv["placa"].map(normalizar_placa)
    csv["litros_f"] = csv["litros"].str.replace(",", ".").astype(float)
    for placa, grupo in csv.groupby("placa_norm"):
        g = grupo.sort_values("km")
        rodado = int(g["km"].iloc[-1]) - int(g["km"].iloc[0])
        litros = float(g["litros_f"].iloc[1:].sum())  # 1º abastecimento não tem trecho anterior
        piso, teto = FAIXA_KM_L[por_placa[placa]["tipo_veiculo"]]
        assert piso <= rodado / litros <= teto, f"consumo implausível: {placa}"

    # 4. valores de multa ∈ tabela CTB (R10)
    assert all(m["valor"] in VALORES_CTB for m in multas)

    # 5. licenciamento pelo final da placa (exceto os 2 'vencendo ≤7 dias' — FR-010, documentados)
    for placa, venc, _situacao in licenciamento:
        v = parse_data(venc)
        if 0 < (v - ANCORA).days <= 7:
            continue
        assert v.month == CAL_DETRAN_MES[int(placa[-1])], f"vencimento fora do calendário: {placa}"

    # 6. estados do semáforo (FR-010): ≥2 vencidos e ≥2 vencendo em ≤7 dias
    assert sum(1 for _, _, s in licenciamento if s == "vencido") >= 2
    assert sum(1 for _, v, _ in licenciamento if 0 < (parse_data(v) - ANCORA).days <= 7) >= 2

    # 7. exatamente 1 veículo caro, leve, fora da demo (FR-009)
    caros = [v for v in veiculos if v["custo_desproporcional"]]
    assert len(caros) == 1 and caros[0]["tipo_veiculo"] == "leve" and not caros[0]["demo_gatilho"]

    # 8. garantia ~25% com revisão programada no marco vigente (FR-012/013, SC-006)
    garantia = [v for v in veiculos if v["em_garantia"]]
    assert 8 <= len(garantia) <= 13
    man = xlsx_manutencao.copy()
    man["tipo_canonico"] = man["tipo"].map(norm_tipo)
    for v in garantia:
        marco = (v["km_atual"] // MARCO_KM) * MARCO_KM
        revisoes = man[(man["placa"] == v["placa"]) & (man["tipo_canonico"] == "revisao_geral")]
        assert (revisoes["km_no_momento"] == marco).any(), f"garantia sem revisão no marco: {v['placa']}"

    # 9. razão de custo corretiva ÷ preventiva entre 3× e 5× (SC-006)
    man["cat"] = man["categoria"].map(norm_categoria)
    media_corr = man.loc[man["cat"] == "corretiva", "valor"].mean()
    media_prev = man.loc[man["cat"] == "preventiva", "valor"].mean()
    assert 3.0 <= media_corr / media_prev <= 5.0
