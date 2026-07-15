# Quickstart — Validação da Spec 001 (Fontes de Dados Simuladas)

**Branch**: `feature/001-fontes-dados-simuladas` | **Date**: 2026-07-14

Guia de validação executável para confirmar que a spec 001 está implementada corretamente.
Cobre os critérios de sucesso SC-001 a SC-006 e os requisitos funcionais FR-001 a FR-013
(incluindo a revisão de realismo de 2026-07-14/15 — ADRs 001–003).
Para os contratos detalhados, ver `contracts/`; para o shape dos dados, ver `data-model.md`.

---

## Pré-requisitos

- Python 3.12+
- Dependências instaladas (ver `research.md` R9): `pandas`, `openpyxl`, `fastapi`,
  `uvicorn`, `numpy` + dev: `pytest`, `httpx`.
- Repositório clonado, na branch `feature/001-fontes-dados-simuladas`.

```bash
# Instalar dependências (gestor a definir em tasks.md — uv ou poetry)
# Exemplo com uv:
uv sync
# ou com pip:
pip install -e .
```

---

## Cenário 1 — Geração dos 4 datasets em um único comando (FR-001, FR-007, SC-001)

**Comando**:
```bash
python data/gerador_dados.py
```

**Resultado esperado** (em < 1 min):
- `data/seeds/veiculos.json` — cadastro de 40 veículos.
- `data/seeds/abastecimento.csv` — CSV de abastecimento.
- `data/seeds/manutencao.xlsx` — XLSX multi-abas (3 abas).
- `data/seeds/licenciamento.sqlite` — base SQLite.
- `data/seeds/limiares_semente.json` — tabela-semente de 9 linhas.
- `data/seeds/gatilho_demo_abastecimento.csv` — CSV-gatilho da demo.
- `data/seeds/INCONSISTENCIAS.md` — documentação das inconsistências.
- `fake_api/multas.json` — payload das multas (servido pela API).

**Verificação manual**:
```bash
ls -la data/seeds/  # confirma os 7 arquivos
ls -la fake_api/multas.json  # confirma o payload da API
```

---

## Cenário 2 — Determinismo / reprodutibilidade (FR-006, SC-004)

**Comando**:
```bash
# Rodar o gerador 2x em diretórios temporários e comparar checksums
python data/gerador_dados.py --output /tmp/run1
python data/gerador_dados.py --output /tmp/run2
sha256sum /tmp/run1/data/seeds/* /tmp/run2/data/seeds/*  # checksums idênticos por arquivo
```

**Resultado esperado**: os checksums SHA-256 de cada arquivo correspondente são idênticos
entre `/tmp/run1` e `/tmp/run2`. Os mesmos 2 veículos da demo (índices 0 e 1 do cadastro)
aparecem à mesma distância dos limiares (4400 km e 166 dias).

**Verificação automatizada**:
```bash
pytest tests/test_gerador_dados.py::test_determinismo -v
```

---

## Cenário 3 — Inconsistências propositais documentadas (FR-003, SC-002, US2)

**Verificação manual**:
```bash
cat data/seeds/INCONSISTENCIAS.md
```

**Resultado esperado**: tabela por fonte listando cada inconsistência, com exemplo concreto
extraído dos dados gerados. Confirmação item a item:

| Fonte | Inconsistência | Como inspecionar |
|---|---|---|
| Abastecimento CSV | placas com/sem hífen | `cut -d, -f1 data/seeds/abastecimento.csv \| sort -u` mostra ambas as grafias |
| Abastecimento CSV | datas em 2 formatos | `cut -d, -f2 data/seeds/abastecimento.csv` mostra `dd/mm/aaaa` e `aaaa-mm-dd` |
| Abastecimento CSV | vírgula decimal | `cut -d, -f3 data/seeds/abastecimento.csv` mostra `45,5` |
| Multas JSON | placas em minúsculas | `jq '.[].placa' fake_api/multas.json` mostra `abc1d23` |
| Multas JSON | campo `cnh` sintético | `jq '.[].cnh' fake_api/multas.json` mostra 11 dígitos |
| Multas JSON | valores tabelados CTB | `jq '[.[].valor] \| unique' fake_api/multas.json` só contém 88.38/130.16/195.23/293.47 (e multiplicadores) |
| Manutenção XLSX | km ausente | `python -c "import pandas as pd; print(pd.read_excel('data/seeds/manutencao.xlsx', sheet_name=None)['Oficina Central'].isna().sum())"` |
| Manutenção XLSX | tipo não padronizado | `python -c "import pandas as pd; print(pd.read_excel('data/seeds/manutencao.xlsx')['tipo'].unique())"` mostra "troca de oleo", "Troca Óleo", etc. |
| Licenciamento SQLite | placas duplicadas | `sqlite3 data/seeds/licenciamento.sqlite "SELECT placa, COUNT(*) FROM licenciamento GROUP BY placa HAVING COUNT(*)>1"` |
| Licenciamento SQLite | vencimentos em formatos mistos | `sqlite3 data/seeds/licenciamento.sqlite "SELECT vencimento FROM licenciamento LIMIT 10"` |

**Verificação automatizada**:
```bash
pytest tests/test_gerador_dados.py::test_inconsistencias -v
```

---

## Cenário 4 — Nenhum dado pessoal real (FR-004, SC-003, US4)

**Verificação**: varrer todos os datasets por campos de condutor; confirmar que só existem
identificadores `COND-NNN` e que nenhum nome/CPF/CNH real aparece.

**Verificação automatizada**:
```bash
pytest tests/test_gerador_dados.py::test_lgpd_sem_dado_pessoal -v
```

**Resultado esperado**: zero ocorrências de nomes próprios, CPFs com formato válido real,
ou CNHs com checksum válido (o `cnh` sintético tem checksum inválido por design —
`research.md` R2).

---

## Cenário 5 — Cenário determinístico da demo (FR-005, US3)

**Verificação**: confirmar que os 2 veículos marcados `demo_gatilho` no cadastro estão à
distância esperada dos limiares.

**Comando**:
```bash
python -c "
import json
veiculos = json.load(open('data/seeds/veiculos.json'))
demo = [v for v in veiculos if v.get('demo_gatilho')]
for v in demo:
    print(v['placa'], v['demo_gatilho_tipo'], 'km_atual=', v['km_atual'])
# Veículo A (km): km_atual=4400, faltam 600 para limite 5000; alerta a 4500
# Veículo B (tempo): última troca_oleo há 166 dias; alerta a 165 (já cruzou), limite 180
"
```

**Verificação do gatilho**: o `gatilho_demo_abastecimento.csv` contém 1 registro cujo `km`
eleva o `km_atual` do veículo A para ≥ 4501 (cruzando o limiar de antecedência 4500). Quando
depositado em `data/inbox/` e ingerido pelo pipeline (spec 003), o motor (spec 004) dispara
o alerta de `troca_oleo` por km — **antes do vencimento** (limite 5000), satisfazendo a
métrica binária de sucesso do briefing.

**Verificação automatizada**:
```bash
pytest tests/test_gerador_dados.py::test_cenario_demo -v
```

---

## Cenário 6 — Endpoint FastAPI das multas (FR-008)

**Subir a API** (em um terminal separado):
```bash
uvicorn fake_api.main:app --port 8000
```

**Verificação** (em outro terminal):
```bash
curl http://localhost:8000/health        # → {"status":"ok"}
curl http://localhost:8000/multas | jq length   # → número de multas (> 0)
curl http://localhost:8000/multas/abc1234 | jq .  # → multas da placa (minúsculas)
```

**Verificação automatizada** (com `TestClient` do FastAPI + httpx, sem subir servidor):
```bash
pytest tests/test_gerador_dados.py::test_endpoint_multas -v
```

---

## Cenário 7 — Coerência física e cenários das specs 005/006 (FR-009..011, SC-005)

**Verificações** (revisão de realismo 2026-07-14 — ADR-003):

| Verificação | Como inspecionar |
|---|---|
| Placas nos 2 formatos (~70% Mercosul) | `jq '[.[].placa] \| map(test("^[A-Z]{3}[0-9][A-Z][0-9]{2}$")) \| (map(select(.)) \| length)' data/seeds/veiculos.json` ≈ 28 |
| Hodômetro monotônico por veículo | ordenar `abastecimento.csv` por placa+data e conferir `km` não-decrescente (exceto anomalias em `INCONSISTENCIAS.md`) |
| Consumo plausível por tipo | km rodados ÷ litros dentro das faixas: leve 8–14 km/L, ambulância 6–10, caminhão 2–5 (research R12) |
| Veículo caro existe | `jq '[.[] \| select(.custo_desproporcional)] \| length' data/seeds/veiculos.json` → `1` (leve, fora dos 2 da demo) |
| Licenciamento pelo final da placa | vencimento no mês do calendário DETRAN-SC (final 1 → março ... final 0 → dezembro) |
| Estados do semáforo | `sqlite3 data/seeds/licenciamento.sqlite "SELECT situacao, COUNT(*) FROM licenciamento GROUP BY situacao"` → ≥2 vencidos; ≥2 vencendo em ≤7 dias |
| Garantia × revisões programadas | `jq '[.[] \| select(.em_garantia)] \| length' data/seeds/veiculos.json` ≈ 10 (~25%); cada um tem registro "Revisão N km" no XLSX dentro do marco vigente (10.000 km/12 meses) |
| Razão corretiva ÷ preventiva | média de `valor` das corretivas ÷ média das preventivas (após normalizar `categoria`) entre 3× e 5× (SC-006 — benchmark do pitch da spec 007) |

**Verificação automatizada**:
```bash
pytest tests/test_gerador_dados.py::test_coerencia_fisica -v
```

---

## Cenário 8 — Suíte completa de testes

```bash
pytest tests/test_gerador_dados.py -v
```

**Resultado esperado**: todos os testes verdes. Cobertura dos critérios de aceite:
- US1 (4 fontes heterogêneas) → Cenário 1.
- US2 (inconsistências) → Cenário 3.
- US3 (cenário da demo) → Cenário 5.
- US4 (LGPD) → Cenário 4.
- FR-008 (endpoint) → Cenário 6.
- FR-009..011 / SC-005 (coerência física, veículo caro, semáforo) → Cenário 7.
- SC-001 (tempo < 1 min) → Cenário 1 (medir com `time python data/gerador_dados.py`).
- SC-004 (determinismo) → Cenário 2.

---

## Próximos passos (fora desta spec)

- **Spec 002** (modelo de dados/banco): formalizar `LIMIAR_CONFIG` com os mesmos valores de
  `limiares_semente.json`, criar tabelas staging + consolidadas + `log_qualidade` + `ALERTA`.
- **Spec 003** (pipeline ETL): construir extratores que consomem os arquivos gerados aqui
  (CSV via pasta `inbox/`, API via `GET /multas`, XLSX via `openpyxl`, SQLite via `sqlite3`),
  aplicando as regras de qualidade que tratam as inconsistências documentadas.
- **Spec 004** (motor): ler `LIMIAR_CONFIG` + dados consolidados e disparar alertas; o
  CSV-gatilho depositado em `data/inbox/` deve fazer o alerta do veículo A surgir no painel.
