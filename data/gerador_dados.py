#!/usr/bin/env python3
"""Gerador das 4 fontes de dados simuladas da frota municipal (spec 001).

Produz, em um único comando determinístico:
  - data/seeds/veiculos.json            cadastro base (referência interna)
  - data/seeds/limiares_semente.json    tabela-semente de limiares (espelho da LIMIAR_CONFIG, spec 002)
  - data/seeds/abastecimento.csv        Fonte 1 (CSV, pasta monitorada)
  - fake_api/multas.json                Fonte 2 (JSON servido pela mini-API FastAPI)
  - data/seeds/manutencao.xlsx          Fonte 3 (XLSX multi-abas)
  - data/seeds/licenciamento.sqlite     Fonte 4 (SQLite legado)
  - data/seeds/gatilho_demo_abastecimento.csv   CSV-gatilho da demo (veículo A)
  - data/seeds/INCONSISTENCIAS.md       documentação das inconsistências propositais

Determinismo: SEED fixa + data-âncora explícita (--data-ancora) → mesmos bytes (FR-006).
Decisões: research.md R1–R13 e docs/decisoes/ADR-001..003.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
DATA_ANCORA_PADRAO = "2026-07-15"
HISTORICO_MESES = 8
JANELA_DIAS = 243  # ~8 meses

# ---------------------------------------------------------------------------
# Parâmetros de calibração (bloco único — definição da fonte simulada, não
# regra de negócio do motor; justificativa no plan.md § Complexity Tracking
# e ADR-003). Os marcos de revisão programada NÃO são redeclarados aqui:
# derivam das linhas revisao_geral de LIMIARES_SEMENTE (fonte única).
# ---------------------------------------------------------------------------

FAIXAS_TIPO = {  # km/mês, consumo (km/L) e tanque por tipo de veículo (R12)
    "leve": {"km_mes": (1000, 2000), "km_por_litro": (8.5, 13.5), "tanque_l": 45},
    "ambulancia": {"km_mes": (2000, 3500), "km_por_litro": (6.3, 9.7), "tanque_l": 60},
    "caminhao": {"km_mes": (1500, 2500), "km_por_litro": (2.2, 4.8), "tanque_l": 150},
}

VALOR_MULTA_CTB = {"leve": 88.38, "media": 130.16, "grave": 195.23, "gravissima": 293.47}
PESO_GRAVIDADE = {"leve": 0.30, "media": 0.45, "grave": 0.15, "gravissima": 0.10}
CODIGO_INFRACAO = {"leve": "5452-1", "media": "5185-1", "grave": "5541-1", "gravissima": "5169-1"}

# Calendário DETRAN-SC: final da placa → (mês, dia) do vencimento do exercício (R11)
CALENDARIO_DETRAN_SC = {
    1: (3, 31), 2: (4, 30), 3: (5, 31), 4: (6, 30), 5: (7, 31),
    6: (8, 31), 7: (9, 30), 8: (10, 31), 9: (11, 30), 0: (12, 30),
}

PROPORCAO_MERCOSUL = 0.70  # ADR-001

CATALOGO_MODELOS = {  # modelos observados em frotas municipais reais (R13)
    "leve": ["Fiat Strada", "Chevrolet Onix", "Chevrolet Spin", "Chevrolet Montana",
             "Volkswagen Gol", "Volkswagen Saveiro", "Renault Kwid"],
    "ambulancia": ["Renault Master", "Fiat Ducato"],
    "caminhao": ["Volkswagen Delivery", "Mercedes-Benz Accelo"],
}
SECRETARIAS_LEVE = ["Administração", "Saúde", "Educação", "Obras", "Meio Ambiente", "Assistência Social"]
ANO_GARANTIA_MIN = 2023  # garantia típica de 3 anos contra a âncora 2026 (R13)

VALOR_PREVENTIVA = {  # faixas de valor (R$) por tipo canônico, base veículo leve
    "troca_oleo": (150, 280), "filtros": (80, 160), "pneus": (1200, 2200), "revisao_geral": (400, 900),
}
MULT_VALOR_TIPO_VEICULO = {"leve": 1.0, "ambulancia": 1.6, "caminhao": 2.8}
RAZAO_CORRETIVA = (3.0, 5.0)  # corretiva = U(3,5) × média das preventivas (SC-006)
PRECO_LITRO = (5.40, 6.40)

GRAFIAS_TIPO = {  # texto livre da Fonte 3, normalizado pela spec 003
    "troca_oleo": ["troca de oleo", "Troca Óleo", "TROCA_OLEO", "troca óleo", "Troca de Oleo"],
    "filtros": ["filtros", "Troca de Filtros", "FILTROS", "filtro de oleo e ar"],
    "pneus": ["pneus", "Troca de Pneus", "PNEUS", "pneu dianteiro/traseiro"],
    "revisao_geral": ["revisao geral", "Revisão Geral", "REVISAO GERAL", "revisão"],
}
GRAFIAS_CATEGORIA = {
    "preventiva": ["preventiva", "Preventiva", "PREVENTIVA", "prev."],
    "corretiva": ["corretiva", "Corretiva", "CORRETIVA", "corr."],
}
ABA_CENTRAL, ABA_NORTE, ABA_TERCEIRIZADA = "Oficina Central", "Oficina Regional Norte", "Manutenção Terceirizada"

# Tabela-semente de limiares (Clarifications 2026-07-14/15; espelho da LIMIAR_CONFIG da spec 002)
LIMIARES_SEMENTE = [
    {"tipo_veiculo": "leve", "tipo_manutencao": "troca_oleo", "limite_km": 5000, "limite_dias": 180, "antecedencia_km": 500, "antecedencia_dias": 15},
    {"tipo_veiculo": "leve", "tipo_manutencao": "filtros", "limite_km": 5000, "limite_dias": 180, "antecedencia_km": 500, "antecedencia_dias": 15},
    {"tipo_veiculo": "leve", "tipo_manutencao": "pneus", "limite_km": 40000, "limite_dias": 720, "antecedencia_km": 2000, "antecedencia_dias": 30},
    {"tipo_veiculo": "leve", "tipo_manutencao": "revisao_geral", "limite_km": 10000, "limite_dias": 365, "antecedencia_km": 1000, "antecedencia_dias": 30},
    {"tipo_veiculo": "ambulancia", "tipo_manutencao": "troca_oleo", "limite_km": 5000, "limite_dias": 180, "antecedencia_km": 500, "antecedencia_dias": 15},
    {"tipo_veiculo": "ambulancia", "tipo_manutencao": "revisao_geral", "limite_km": 10000, "limite_dias": 365, "antecedencia_km": 1000, "antecedencia_dias": 30},
    {"tipo_veiculo": "caminhao", "tipo_manutencao": "troca_oleo", "limite_km": 10000, "limite_dias": 180, "antecedencia_km": 1000, "antecedencia_dias": 15},
    {"tipo_veiculo": "caminhao", "tipo_manutencao": "pneus", "limite_km": 60000, "limite_dias": 720, "antecedencia_km": 3000, "antecedencia_dias": 30},
    {"tipo_veiculo": "caminhao", "tipo_manutencao": "revisao_geral", "limite_km": 30000, "limite_dias": 365, "antecedencia_km": 1500, "antecedencia_dias": 30},
]

# Marco das revisões programadas de fabricante = limite_km da revisao_geral leve (10.000 km — fonte única)
MARCO_REVISAO_KM = next(l["limite_km"] for l in LIMIARES_SEMENTE
                        if l["tipo_veiculo"] == "leve" and l["tipo_manutencao"] == "revisao_geral")

TIPOS_APLICAVEIS = {
    "leve": ["troca_oleo", "filtros", "pneus", "revisao_geral"],
    "ambulancia": ["troca_oleo", "revisao_geral"],
    "caminhao": ["troca_oleo", "pneus", "revisao_geral"],
}


# ---------------------------------------------------------------------------
# Helpers determinísticos
# ---------------------------------------------------------------------------

def _u(rng: np.random.Generator, a: float, b: float) -> float:
    return float(rng.uniform(a, b))


def _escolha(rng: np.random.Generator, opcoes: list):
    return opcoes[int(rng.integers(0, len(opcoes)))]


def gerar_placa(rng: np.random.Generator, mercosul: bool) -> str:
    letras = "".join(chr(65 + int(rng.integers(0, 26))) for _ in range(3))
    if mercosul:  # AAA9A99
        return f"{letras}{int(rng.integers(0, 10))}{chr(65 + int(rng.integers(0, 26)))}{int(rng.integers(0, 10))}{int(rng.integers(0, 10))}"
    return f"{letras}{''.join(str(int(rng.integers(0, 10))) for _ in range(4))}"  # AAA9999


def _dv_cnh(base9: str) -> str:
    """Dígitos verificadores da CNH (módulo 11). Usado pelo teste LGPD para provar invalidez."""
    soma1 = sum(int(d) * p for d, p in zip(base9, range(9, 0, -1)))
    dv1 = soma1 % 11
    dv1 = 0 if dv1 >= 10 else dv1
    soma2 = sum(int(d) * p for d, p in zip(base9, range(1, 10)))
    dv2 = soma2 % 11
    dv2 = 0 if dv2 >= 10 else dv2
    return f"{dv1}{dv2}"


def cnh_sintetica(rng: np.random.Generator) -> str:
    """CNH sintética com DV propositalmente inválido (R2): calcula o DV correto e o perturba."""
    base = "".join(str(int(rng.integers(0, 10))) for _ in range(9))
    dv = _dv_cnh(base)
    dv_invalido = f"{(int(dv[0]) + 1) % 10}{dv[1]}"
    return base + dv_invalido


def fmt_moeda(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def serial_excel(d: date) -> int:
    return (d - date(1899, 12, 30)).days


# ---------------------------------------------------------------------------
# Cadastro base (T007) e série de hodômetro (T008)
# ---------------------------------------------------------------------------

def gerar_veiculos(rng: np.random.Generator, ancora: date) -> list[dict]:
    """40 veículos: 30 leves (índices 0–29), 6 ambulâncias (30–35), 4 caminhões (36–39).

    Índice 0 = demo A (gatilho km, ao vivo); índice 1 = demo B (gatilho tempo, 166 dias);
    índice 2 = veículo de custo desproporcional (FR-009). Garantia: ~25% (ano >= 2023, R13).
    """
    tipos = ["leve"] * 30 + ["ambulancia"] * 6 + ["caminhao"] * 4
    # 10/40 em garantia: leves 3..9 (7), ambulâncias 30..31 (2), caminhão 36 (1)
    indices_garantia = set(range(3, 10)) | {30, 31, 36}

    placas: set[str] = set()
    veiculos: list[dict] = []
    for i, tipo in enumerate(tipos):
        mercosul = _u(rng, 0, 1) < PROPORCAO_MERCOSUL
        placa = gerar_placa(rng, mercosul)
        while placa in placas:
            placa = gerar_placa(rng, mercosul)
        placas.add(placa)

        faixa = FAIXAS_TIPO[tipo]
        if i == 0:  # demo A: uso urbano típico
            ano, km_mes = 2021, 1500
        elif i == 1:  # demo B: roda pouco — é exatamente o caso do gatilho por tempo (spec 004 US2)
            ano, km_mes = 2020, 450
        elif i == 2:  # veículo caro: velho, roda muito, consome muito
            ano, km_mes = 2016, 1900
        elif i in indices_garantia:
            ano = int(rng.integers(ANO_GARANTIA_MIN, ancora.year + 1))
            km_mes = int(rng.integers(*faixa["km_mes"]))
        else:
            ano = int(rng.integers(2015, ANO_GARANTIA_MIN))
            km_mes = int(rng.integers(*faixa["km_mes"]))

        if tipo == "ambulancia":
            secretaria = "Saúde"
        elif tipo == "caminhao":
            secretaria = _escolha(rng, ["Obras", "Meio Ambiente"])
        else:
            secretaria = _escolha(rng, SECRETARIAS_LEVE)

        piso, teto = faixa["km_por_litro"]
        consumo = round(piso + 0.05, 2) if i == 2 else round(_u(rng, piso + 0.2, teto - 0.2), 2)

        em_garantia = ano >= ANO_GARANTIA_MIN
        veiculos.append({
            "_consumo": consumo,  # km/L fixo do veículo (interno; removido do veiculos.json)
            "placa": placa,
            "tipo_veiculo": tipo,
            "modelo": _escolha(rng, CATALOGO_MODELOS[tipo]),
            "ano": ano,
            "em_garantia": em_garantia,
            "secretaria": secretaria,
            "km_mes": km_mes,
            "km_atual": 0,  # preenchido por gerar_serie_hodometro
            "demo_gatilho": i in (0, 1),
            "demo_gatilho_tipo": {0: "km", 1: "tempo"}.get(i),
            "custo_desproporcional": i == 2,
            "condutores": [],  # preenchido abaixo
        })

    # Pool de condutores sintéticos COND-NNN (FR-004): 1–3 por veículo, de um pool global de 60
    for i, v in enumerate(veiculos):
        n = 1 + int(rng.integers(0, 3))
        base = int(rng.integers(1, 61))
        v["condutores"] = sorted({f"COND-{((base + k * 7) % 60) + 1:03d}" for k in range(n)})
    return veiculos


def gerar_serie_hodometro(rng: np.random.Generator, veiculos: list[dict], ancora: date) -> dict[str, dict]:
    """Janela de 8 meses por veículo: km_inicial → km_atual, monotônica (R12).

    O mapeamento km ↔ data é linear dentro da janela (modelo simples e consistente
    entre CSV de abastecimento e XLSX de manutenção — SC-005/FR-011).
    """
    inicio = ancora - timedelta(days=JANELA_DIAS)
    series: dict[str, dict] = {}
    for i, v in enumerate(veiculos):
        idade = max(1, ancora.year - v["ano"])
        if i == 0:  # demo A: valores fixos para o posicionamento exato (R4)
            rodado, km_inicial = 12000, 42000
        elif i == 1:  # demo B
            rodado, km_inicial = 3600, 30000
        elif v["em_garantia"]:
            # posiciona o km_atual entre 1.000 e 7.500 km após o último marco de revisão,
            # garantindo marco dentro da janela e sem alerta espúrio de revisao_geral
            rodado = int(round(v["km_mes"] * HISTORICO_MESES * _u(rng, 0.92, 1.08)))
            marco = max(MARCO_REVISAO_KM,
                        int(round(idade * v["km_mes"] * 12 * 0.8 / MARCO_REVISAO_KM)) * MARCO_REVISAO_KM)
            # teto ≥ 1500 evita range invertido em np.uniform se rodado < 1500 (guard defensivo)
            offset = int(_u(rng, 1000, min(7500, max(1500, rodado - 500))))
            km_atual = marco + offset
            km_inicial = km_atual - rodado
            if km_inicial <= 0:  # veículo muito novo: desloca o marco para cima
                km_inicial = int(_u(rng, 500, 2000))
                km_atual = km_inicial + rodado
            series[v["placa"]] = {"km_inicial": km_inicial, "rodado": km_atual - km_inicial, "inicio": inicio}
            v["km_atual"] = km_atual
            continue
        else:
            rodado = int(round(v["km_mes"] * HISTORICO_MESES * _u(rng, 0.92, 1.08)))
            km_estimado = int(idade * v["km_mes"] * 12 * _u(rng, 0.6, 0.9))
            km_inicial = max(200, km_estimado - rodado)
        v["km_atual"] = km_inicial + rodado
        series[v["placa"]] = {"km_inicial": km_inicial, "rodado": rodado, "inicio": inicio}
    return series


def data_por_km(serie: dict, km: int) -> date:
    frac = (km - serie["km_inicial"]) / serie["rodado"]
    return serie["inicio"] + timedelta(days=round(frac * JANELA_DIAS))


def km_por_data(serie: dict, d: date) -> int:
    frac = (d - serie["inicio"]).days / JANELA_DIAS
    return int(round(serie["km_inicial"] + frac * serie["rodado"]))


# ---------------------------------------------------------------------------
# Fonte 1 — Abastecimento CSV (T012 + inconsistências T020)
# ---------------------------------------------------------------------------

def _grafia_placa_csv(rng: np.random.Generator, placa: str) -> str:
    return f"{placa[:3]}-{placa[3:]}" if _u(rng, 0, 1) < 0.5 else placa


def _grafia_data_csv(rng: np.random.Generator, d: date) -> str:
    return d.strftime("%d/%m/%Y") if _u(rng, 0, 1) < 0.5 else d.isoformat()


def gerar_abastecimento(rng: np.random.Generator, veiculos: list[dict], series: dict) -> list[dict]:
    linhas: list[dict] = []
    for v in veiculos:
        serie = series[v["placa"]]
        faixa = FAIXAS_TIPO[v["tipo_veiculo"]]
        consumo = v["_consumo"]
        tanque = faixa["tanque_l"]
        km = serie["km_inicial"] + int(_u(rng, 50, 300))
        primeiro = True
        while km < v["km_atual"] - 30:
            if primeiro:
                litros = round(tanque * _u(rng, 0.5, 0.8), 1)
                primeiro = False
            else:
                litros = round((km - km_anterior) / consumo, 1)
            preco = _u(rng, *PRECO_LITRO)
            d = data_por_km(serie, km)
            linhas.append({
                "placa": _grafia_placa_csv(rng, v["placa"]),
                "data": _grafia_data_csv(rng, d),
                "litros": f"{litros:.1f}".replace(".", ","),
                "valor": fmt_moeda(litros * preco),
                "condutor": _escolha(rng, v["condutores"]),
                "km": int(km),
            })
            km_anterior = km
            passo = tanque * consumo * _u(rng, 0.55, 0.85)
            km = int(km + passo)
    return linhas


def gerar_gatilho_demo(rng: np.random.Generator, veiculos: list[dict], ancora: date) -> list[dict]:
    """CSV-gatilho (FR-005): 1 abastecimento do veículo A que leva km_desde_ultima de 4400 a 4550
    (cruza a antecedência 4500 sem atingir o limite 5000 — alerta ANTES do vencimento)."""
    a = veiculos[0]
    km_gatilho = a["km_atual"] + 150
    litros = round(150 / a["_consumo"] + 20, 1)  # completa o tanque
    return [{
        "placa": f"{a['placa'][:3]}-{a['placa'][3:]}",
        "data": ancora.strftime("%d/%m/%Y"),
        "litros": f"{litros:.1f}".replace(".", ","),
        "valor": fmt_moeda(litros * 5.89),
        "condutor": a["condutores"][0],
        "km": int(km_gatilho),
    }]


# ---------------------------------------------------------------------------
# Fonte 3 — Manutenção XLSX (T013 + inconsistências T022 + demo T027/T028)
# ---------------------------------------------------------------------------

def gerar_manutencao(rng: np.random.Generator, veiculos: list[dict], series: dict, ancora: date) -> list[dict]:
    eventos: list[dict] = []

    def add(v, tipo_canonico, km_evento, categoria, aba=None, tipo_texto=None, ancora_demo=False):
        serie = series[v["placa"]]
        km_evento = int(km_evento)
        faixa_valor = VALOR_PREVENTIVA[tipo_canonico]
        valor = round(_u(rng, *faixa_valor) * MULT_VALOR_TIPO_VEICULO[v["tipo_veiculo"]], 2)
        eventos.append({
            "placa": v["placa"],
            "_data": data_por_km(serie, km_evento),
            "tipo": tipo_texto or _escolha(rng, GRAFIAS_TIPO[tipo_canonico]),
            "_tipo_canonico": tipo_canonico,
            "categoria": _escolha(rng, GRAFIAS_CATEGORIA[categoria]),
            "_categoria_canonica": categoria,
            "km_no_momento": km_evento,
            "valor": valor,
            "_aba": aba or (_escolha(rng, [ABA_CENTRAL, ABA_CENTRAL, ABA_NORTE, ABA_NORTE, ABA_TERCEIRIZADA])),
            "_protegido": ancora_demo,  # âncora da demo: imune a km-ausente (T028)
        })
        return eventos[-1]

    limiar = {(l["tipo_veiculo"], l["tipo_manutencao"]): l for l in LIMIARES_SEMENTE}

    for i, v in enumerate(veiculos):
        serie = series[v["placa"]]
        rodado, km_ini, km_fim = serie["rodado"], serie["km_inicial"], v["km_atual"]
        demo = v["demo_gatilho"]

        # --- troca_oleo: âncora (evento mais recente) ---
        if i == 0:      # demo A: exatamente 4400 km desde a última (R4)
            km_anc = km_fim - 4400
            add(v, "troca_oleo", km_anc, "preventiva", ancora_demo=True)
        elif i == 1:    # demo B: exatamente 166 dias desde a última (R4)
            d_anc = ancora - timedelta(days=166)
            km_anc = km_por_data(serie, d_anc)
            add(v, "troca_oleo", km_anc, "preventiva", ancora_demo=True)
        else:
            lim = limiar[(v["tipo_veiculo"], "troca_oleo")]["limite_km"]
            teto = min(lim - 1500, rodado - 200)
            km_anc = km_fim - int(_u(rng, 500, max(600, teto)))
            add(v, "troca_oleo", km_anc, "preventiva")
        # cadência anterior dentro da janela
        lim_oleo = limiar[(v["tipo_veiculo"], "troca_oleo")]["limite_km"]
        km_prev = km_anc - int(lim_oleo * _u(rng, 0.9, 1.1))
        while km_prev > km_ini + 100:
            add(v, "troca_oleo", km_prev, "preventiva")
            km_prev -= int(lim_oleo * _u(rng, 0.9, 1.1))

        # --- filtros (apenas leves) ---
        if "filtros" in TIPOS_APLICAVEIS[v["tipo_veiculo"]]:
            if demo:
                km_f = km_fim - int(_u(rng, 1500, 2500)) if i == 0 else km_fim - int(_u(rng, 800, 1500))
                add(v, "filtros", max(km_f, km_ini + 100), "preventiva", ancora_demo=True)
            else:
                km_f = km_fim - int(_u(rng, 500, min(3500, rodado - 200)))
                add(v, "filtros", km_f, "preventiva")

        # --- revisao_geral ---
        if v["em_garantia"]:
            # revisões programadas nos marcos do fabricante, na aba de terceirizada (R13)
            marco = (km_fim // MARCO_REVISAO_KM) * MARCO_REVISAO_KM
            while marco > km_ini:
                grafia = _escolha(rng, [f"Revisão {marco:,} km".replace(",", "."),
                                        f"REVISAO {marco}",
                                        f"revisão dos {marco // 1000} mil"])
                add(v, "revisao_geral", marco, "preventiva", aba=ABA_TERCEIRIZADA,
                    tipo_texto=grafia, ancora_demo=True)
                marco -= MARCO_REVISAO_KM
        else:
            km_r = km_fim - int(_u(rng, 1000, min(7000, rodado - 200)))
            add(v, "revisao_geral", max(km_r, km_ini + 100), "preventiva", ancora_demo=demo)

        # --- pneus ---
        if "pneus" in TIPOS_APLICAVEIS[v["tipo_veiculo"]]:
            km_p = int(_u(rng, km_ini + 200, km_fim - 200))
            add(v, "pneus", km_p, "preventiva", ancora_demo=demo)

        # --- corretivas (nunca nos veículos da demo — T028) ---
        if not demo:
            n_corretivas = 3 if v["custo_desproporcional"] else int(_escolha(rng, [0, 1, 1, 2]))
            for _ in range(n_corretivas):
                tipo_c = _escolha(rng, [t for t in TIPOS_APLICAVEIS[v["tipo_veiculo"]] if t != "troca_oleo"])
                km_c = int(_u(rng, km_ini + 300, km_fim - 100))
                ev = add(v, tipo_c, km_c, "corretiva")
                ev["_corretiva_pendente"] = True

    # valor das corretivas: U(3,5) × média das preventivas (SC-006)
    media_prev = float(np.mean([e["valor"] for e in eventos if e["_categoria_canonica"] == "preventiva"]))
    for e in eventos:
        if e.pop("_corretiva_pendente", False):
            fator = _u(rng, *RAZAO_CORRETIVA)
            if any(vv["custo_desproporcional"] and vv["placa"] == e["placa"] for vv in veiculos):
                fator = _u(rng, 4.2, 5.0)  # o veículo caro concentra as corretivas mais caras
            e["valor"] = round(media_prev * fator, 2)

    # km ausente em ~15% dos registros elegíveis. Protegidos (ADR-003, adendo 2026-07-15b):
    # âncoras da demo, marcos de garantia E o evento de maior km de cada (placa, tipo) —
    # é ele que o motor usa em km_desde_ultima; anulá-lo faria o cálculo cair num evento
    # anterior e cruzar o limiar, gerando alerta espúrio em veículo não-demo.
    ancora_por_par: dict[tuple[str, str], dict] = {}
    for e in eventos:
        chave = (e["placa"], e["_tipo_canonico"])
        atual = ancora_por_par.get(chave)
        if atual is None or e["km_no_momento"] > atual["km_no_momento"]:
            ancora_por_par[chave] = e
    ids_ancora = {id(e) for e in ancora_por_par.values()}
    elegiveis = [e for e in eventos if not e["_protegido"] and id(e) not in ids_ancora]
    n_ausentes = int(round(len(elegiveis) * 0.15))
    indices = rng.choice(len(elegiveis), size=n_ausentes, replace=False)
    for idx in indices:
        elegiveis[int(idx)]["km_no_momento"] = None

    # data em formatos mistos: aaaa-mm-dd (TEXT) ou serial Excel (INTEGER)
    for e in eventos:
        d = e.pop("_data")
        e["data"] = serial_excel(d) if _u(rng, 0, 1) < 0.3 else d.isoformat()
    return eventos


# ---------------------------------------------------------------------------
# Fonte 2 — Multas JSON (T014 + T021) e Fonte 4 — Licenciamento SQLite (T015 + T023)
# ---------------------------------------------------------------------------

def gerar_multas(rng: np.random.Generator, veiculos: list[dict], ancora: date, n_multas: int = 100) -> list[dict]:
    inicio = ancora - timedelta(days=JANELA_DIAS)
    # distribuição enviesada (R10): o veículo caro e 3 "reincidentes" concentram as multas
    pesos = np.array([12.0 if v["custo_desproporcional"]
                      else 5.0 if i in (4, 12, 31)
                      else 0.5 for i, v in enumerate(veiculos)])
    pesos = pesos / pesos.sum()
    gravidades = list(PESO_GRAVIDADE)
    pesos_grav = np.array([PESO_GRAVIDADE[g] for g in gravidades])
    cnh_por_condutor: dict[str, str] = {}

    multas = []
    for _ in range(n_multas):
        v = veiculos[int(rng.choice(len(veiculos), p=pesos))]
        gravidade = gravidades[int(rng.choice(len(gravidades), p=pesos_grav))]
        valor = VALOR_MULTA_CTB[gravidade]
        if gravidade == "gravissima" and _u(rng, 0, 1) < 0.2:
            valor = round(valor * int(_escolha(rng, [2, 3])), 2)
        condutor = _escolha(rng, v["condutores"])
        if condutor not in cnh_por_condutor:
            cnh_por_condutor[condutor] = cnh_sintetica(rng)
        d = inicio + timedelta(days=int(_u(rng, 0, JANELA_DIAS)))
        multas.append({
            "placa": v["placa"].lower(),  # inconsistência propositais (R7)
            "data": d.isoformat(),
            "gravidade": gravidade,
            "valor": valor,
            "condutor": condutor,
            "cnh": cnh_por_condutor[condutor],
            "situacao": "paga" if _u(rng, 0, 1) < 0.65 else "pendente",
            "codigo_infracao": CODIGO_INFRACAO[gravidade],
        })
    return sorted(multas, key=lambda m: m["data"])


def _vencimento_calendario(placa: str, exercicio: int) -> date:
    mes, dia = CALENDARIO_DETRAN_SC[int(placa[-1])]
    return date(exercicio, mes, dia)


def gerar_licenciamento(rng: np.random.Generator, veiculos: list[dict], ancora: date) -> list[dict]:
    """Vencimento pelo final da placa (R11). Estados p/ semáforo da 005 (FR-010):
    ≥2 vencidos (exercício anterior não renovado) e ≥2 vencendo em ≤7 dias
    (dia fora do calendário oficial — inconsistência de legado, documentada)."""
    nao_demo = [i for i in range(len(veiculos)) if i not in (0, 1)]
    idx_vencendo = nao_demo[1:3]     # 2 veículos vencendo em ≤7 dias
    idx_vencidos = nao_demo[3:5]     # 2 veículos com exercício anterior vencido
    idx_duplicados = nao_demo[5:13]  # ~20% com registro antigo duplicado

    registros = []
    for i, v in enumerate(veiculos):
        placa = v["placa"]
        if i in idx_vencendo:
            venc = ancora + timedelta(days=3 if i == idx_vencendo[0] else 6)
            registros.append({"placa": placa, "_venc": venc, "situacao": "em_dia"})
        elif i in idx_vencidos:
            registros.append({"placa": placa, "_venc": _vencimento_calendario(placa, ancora.year - 1),
                              "situacao": "vencido"})
        else:
            registros.append({"placa": placa, "_venc": _vencimento_calendario(placa, ancora.year),
                              "situacao": "em_dia"})
        if i in idx_duplicados:  # duplicata: registro do exercício anterior não expurgado
            registros.append({"placa": placa, "_venc": _vencimento_calendario(placa, ancora.year - 1),
                              "situacao": "vencido"})

    # formatos mistos de escrita (R6): dd/mm/aaaa TEXT · aaaa-mm-dd TEXT · serial Excel INTEGER
    for r in registros:
        venc = r.pop("_venc")
        sorteio = _u(rng, 0, 1)
        if sorteio < 0.4:
            r["vencimento"] = venc.strftime("%d/%m/%Y")
        elif sorteio < 0.8:
            r["vencimento"] = venc.isoformat()
        else:
            r["vencimento"] = serial_excel(venc)
    return registros


# ---------------------------------------------------------------------------
# Documentação das inconsistências (T024) e escrita dos artefatos (T016)
# ---------------------------------------------------------------------------

def gerar_inconsistencias_md(abastecimento, multas, manutencao, licenciamento, ancora: date) -> str:
    ex_hifen = next(l["placa"] for l in abastecimento if "-" in l["placa"])
    ex_data_br = next(l["data"] for l in abastecimento if "/" in l["data"])
    ex_data_iso = next(l["data"] for l in abastecimento if "-" in l["data"] and "/" not in l["data"])
    ex_virgula = next(l["litros"] for l in abastecimento if "," in l["litros"])
    ex_placa_min = multas[0]["placa"]
    n_km_ausente = sum(1 for e in manutencao if e["km_no_momento"] is None)
    grafias_tipo = sorted({e["tipo"] for e in manutencao})[:6]
    placas_lic = [r["placa"] for r in licenciamento]
    duplicadas = sorted({p for p in placas_lic if placas_lic.count(p) > 1})

    return f"""# Inconsistências propositais dos datasets simulados (FR-003 · SC-002)

Gerado por `data/gerador_dados.py` (semente {SEED}, data-âncora {ancora.isoformat()}).
Cada inconsistência é insumo das regras de qualidade do pipeline (spec 003).

## Fonte 1 — Abastecimento (CSV)

| Inconsistência | Exemplo gerado | Tratamento (spec 003) | Motivo em `log_qualidade` |
|---|---|---|---|
| Placa com e sem hífen (~50/50) | `{ex_hifen}` | normalização canônica (regex dual, ADR-001) | — (normaliza) |
| Datas em 2 formatos | `{ex_data_br}` e `{ex_data_iso}` | parsing tolerante | `data_invalida` se não parsear |
| Litros/valor com vírgula decimal | `{ex_virgula}` | conversão decimal | — (normaliza) |

## Fonte 2 — Multas (JSON/API)

| Inconsistência | Exemplo gerado | Tratamento (spec 003) | Motivo |
|---|---|---|---|
| Placa em minúsculas | `{ex_placa_min}` | normalização canônica | — (normaliza) |
| `cnh` presente (dado pessoal sintético, DV inválido) | 11 dígitos | **descartada na carga** (minimização LGPD, FR-011 da spec 003) | — |
| `gravidade`/`codigo_infracao` fonte-apenas | — | ignorados na consolidação (ERD intacto) | — |

## Fonte 3 — Manutenção (XLSX, 3 abas)

| Inconsistência | Exemplo gerado | Tratamento (spec 003) | Motivo |
|---|---|---|---|
| Tipo em texto livre | {", ".join(f"`{g}`" for g in grafias_tipo)} | vocabulário canônico (`troca_oleo`…) | `tipo_desconhecido` se não mapear |
| Categoria com grafias variadas | `Preventiva`, `CORRETIVA`, `prev.` | normaliza p/ `preventiva`\\|`corretiva` | idem |
| `km_no_momento` ausente ({n_km_ausente} registros, ~15%) | célula vazia | aceito (nullable); motor trata como km não confiável | — |
| Datas TEXT × serial Excel | `2026-03-15` / `46068` | parsing tolerante | `data_invalida` |

**Anomalias protegidas**: nunca recebem km ausente — os registros-âncora dos 2 veículos
da demo, as revisões programadas de garantia **e o evento mais recente de cada
(placa, tipo de manutenção)**, que é o que o motor usa em `km_desde_ultima`. Isso preserva
o invariante "demais veículos longe dos limiares, sem alertas espúrios" (ADR-003, adendo
2026-07-15b; regressão coberta por `test_sem_alertas_espurios`).

## Fonte 4 — Licenciamento (SQLite)

| Inconsistência | Exemplo gerado | Tratamento (spec 003) | Motivo |
|---|---|---|---|
| Placas duplicadas ({len(duplicadas)} veículos c/ 2 registros) | `{duplicadas[0] if duplicadas else "-"}` | dedup por (placa, vencimento mais recente) | `duplicado` |
| Vencimento em 3 formatos | `dd/mm/aaaa` TEXT · `aaaa-mm-dd` TEXT · serial INTEGER | parsing tolerante | `data_invalida` |
| **2 vencimentos com dia fora do calendário oficial** (vencendo em ≤7 dias da âncora — FR-010) | — | data válida, mês pode divergir do final da placa (legado) | — |

## Invariantes de coerência (SC-005/SC-006 — não são inconsistências)

- Hodômetro monotônico por veículo, consistente entre CSV e XLSX (mapeamento km↔data linear na janela).
- Consumo derivado dentro das faixas por tipo; valores de multa ∈ tabela CTB.
- Razão de custo corretiva ÷ preventiva calibrada em 3–5× (benchmark do pitch, spec 007).
"""


def _normalizar_zip(caminho: Path) -> None:
    """Reescreve o zip do XLSX com timestamps fixos e entradas ordenadas (determinismo R1).

    O openpyxl sobrescreve `dcterms:modified` com o horário do save — o campo é
    fixado aqui para que duas execuções produzam bytes idênticos (FR-006/SC-004).
    """
    import re as _re
    with zipfile.ZipFile(caminho) as z:
        itens = [(nome, z.read(nome)) for nome in sorted(z.namelist())]
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in itens:
            if nome == "docProps/core.xml":
                dados = _re.sub(
                    rb"<dcterms:modified[^>]*>[^<]*</dcterms:modified>",
                    b'<dcterms:modified xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:modified>',
                    dados,
                )
            z.writestr(zipfile.ZipInfo(nome, date_time=(1980, 1, 1, 0, 0, 0)), dados)


def gerar_tudo(raiz: Path, ancora: date) -> None:
    rng = np.random.default_rng(SEED)
    seeds = raiz / "data" / "seeds"
    fake_api = raiz / "fake_api"
    seeds.mkdir(parents=True, exist_ok=True)
    fake_api.mkdir(parents=True, exist_ok=True)
    (raiz / "data" / "inbox").mkdir(parents=True, exist_ok=True)

    veiculos = gerar_veiculos(rng, ancora)
    series = gerar_serie_hodometro(rng, veiculos, ancora)
    abastecimento = gerar_abastecimento(rng, veiculos, series)
    manutencao = gerar_manutencao(rng, veiculos, series, ancora)
    multas = gerar_multas(rng, veiculos, ancora)
    licenciamento = gerar_licenciamento(rng, veiculos, ancora)
    gatilho = gerar_gatilho_demo(rng, veiculos, ancora)

    # --- veiculos.json + limiares_semente.json ---
    publicos = [{k: v for k, v in veic.items() if not k.startswith("_")} for veic in veiculos]
    (seeds / "veiculos.json").write_text(
        json.dumps(publicos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (seeds / "limiares_semente.json").write_text(
        json.dumps(LIMIARES_SEMENTE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # --- Fonte 1: CSV (+ gatilho) ---
    colunas = ["placa", "data", "litros", "valor", "condutor", "km"]
    pd.DataFrame(abastecimento, columns=colunas).to_csv(seeds / "abastecimento.csv", index=False)
    pd.DataFrame(gatilho, columns=colunas).to_csv(seeds / "gatilho_demo_abastecimento.csv", index=False)

    # --- Fonte 2: multas.json ---
    (fake_api / "multas.json").write_text(
        json.dumps(multas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # --- Fonte 3: XLSX multi-abas ---
    cols_xlsx = ["placa", "data", "tipo", "categoria", "km_no_momento", "valor"]
    caminho_xlsx = seeds / "manutencao.xlsx"
    with pd.ExcelWriter(caminho_xlsx, engine="openpyxl") as writer:
        # propriedades fixas: sem timestamp de criação → bytes determinísticos (FR-006/R1)
        writer.book.properties.created = datetime(2026, 1, 1)
        writer.book.properties.modified = datetime(2026, 1, 1)
        for aba in (ABA_CENTRAL, ABA_NORTE, ABA_TERCEIRIZADA):
            df = pd.DataFrame([{c: e[c] for c in cols_xlsx} for e in manutencao if e["_aba"] == aba],
                              columns=cols_xlsx)
            df.to_excel(writer, sheet_name=aba, index=False)
    _normalizar_zip(caminho_xlsx)

    # --- Fonte 4: SQLite ---
    caminho_sqlite = seeds / "licenciamento.sqlite"
    caminho_sqlite.unlink(missing_ok=True)
    con = sqlite3.connect(caminho_sqlite)
    con.execute("CREATE TABLE licenciamento (placa TEXT NOT NULL, vencimento, situacao TEXT)")
    con.executemany("INSERT INTO licenciamento VALUES (?, ?, ?)",
                    [(r["placa"], r["vencimento"], r["situacao"]) for r in licenciamento])
    con.commit()
    con.close()

    # --- documentação das inconsistências ---
    (seeds / "INCONSISTENCIAS.md").write_text(
        gerar_inconsistencias_md(abastecimento, multas, manutencao, licenciamento, ancora),
        encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera as 4 fontes simuladas da frota municipal (spec 001).")
    parser.add_argument("--output", default=None,
                        help="Diretório-raiz de saída (default: raiz do repositório).")
    parser.add_argument("--data-ancora", default=DATA_ANCORA_PADRAO,
                        help=f"Data-âncora ISO de todas as datas relativas (default: {DATA_ANCORA_PADRAO}). "
                             "Regenerar com a âncora do dia da apresentação antes da demo (spec 007 FR-002).")
    args = parser.parse_args()
    try:
        ancora = date.fromisoformat(args.data_ancora)
    except ValueError:
        parser.error(f"--data-ancora inválida: {args.data_ancora!r} (formato esperado: AAAA-MM-DD)")
    raiz = Path(args.output).resolve() if args.output else Path(__file__).resolve().parent.parent
    if args.output and not raiz.parent.exists():
        parser.error(f"--output inválido: o diretório pai de {raiz} não existe")
    gerar_tudo(raiz, ancora)
    print(f"Datasets gerados em {raiz} (semente {SEED}, âncora {ancora.isoformat()}).")


if __name__ == "__main__":
    main()
