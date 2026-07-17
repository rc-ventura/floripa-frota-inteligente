# Implementation Plan: Pipeline ETL de Integração das Fontes

**Branch**: `feature/003-pipeline-etl` | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-pipeline-etl/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Pipeline em três estágios (Extract → Validate & Transform → Load, arquitetura §3) que integra
as 4 fontes heterogêneas (CSV em pasta monitorada, API JSON de multas, XLSX multi-abas,
SQLite legado) no banco consolidado da spec 002. Um extrator por fonte deposita dado **bruto**
no `stg_*` com carimbo de carga e origem (constitution II); a transformação normaliza placa
(regex dual ADR-001), datas (3 formatos, incluindo serial Excel), decimais com vírgula e
vocabulários, rejeitando o inválido para `log_qualidade` com motivo; a carga faz **upsert
idempotente** pelas chaves UNIQUE já garantidas no banco (contrato 002/ADR-004), descarta os
campos fonte-apenas de multas (`cnh`/`gravidade`/`codigo_infracao` — FR-011, LGPD) e atualiza
`veiculo.km_atual` com a maior leitura válida de hodômetro (ADR-002). Novidade é detectada por
hash de conteúdo (arquivo re-depositado ou renomeado não duplica nada); falha de uma fonte não
derruba o ciclo das demais (US4). Ponto de entrada único `python -m pipeline.run_etl` /
`executar_ciclo()`, invocável pelo agendador da spec 004 — é o elo demo-crítico entre o CSV
depositado na pasta e o alerta surgindo no painel.

## Technical Context

**Language/Version**: Python 3.12+ (decisão D1; ambiente atual 3.13).

**Primary Dependencies**:
- `pandas` + `openpyxl` (já no projeto) — leitura CSV/XLSX multi-abas (D1).
- `sqlalchemy>=2.0` (já no projeto) — staging/consolidadas via `db.config.get_engine()`
  (contrato 002: nunca criar URL própria) e upserts por dialeto (`sqlite`/`postgresql`
  `insert().on_conflict_*`).
- `httpx>=0.27` — extrator de multas (promovida do grupo dev para o principal; research R9).
- `sqlite3` (stdlib) — leitura da base legada de licenciamento.
- Reusa `pytest` para os testes de aceitação.

**Storage**: mesmo banco da spec 002 (SQLite default / PostgreSQL 16 via `DATABASE_URL`).
O pipeline escreve **apenas** `stg_*` (append), consolidadas (upsert) e `log_qualidade` —
nenhuma tabela nova, nenhum estado fora do banco (research R1).

**Testing**: `pytest` em `tests/test_pipeline.py` — staging bruto + carimbo (US1),
inconsistências da spec 001 normalizadas/rejeitadas com motivo (US2/SC-002), dupla execução
com estado idêntico (US3/SC-001), fonte fora do ar não derruba ciclo (US4/SC-005),
rastreabilidade (SC-003), descarte LGPD de `cnh` (FR-011).

**Target Platform**: local (dev) e container da demo (D6); fake_api acessível por URL
configurável (`http://localhost:8000` local, `http://fake_api:8000` no compose da spec 007).

**Project Type**: biblioteca interna (`pipeline/`) + CLI de ciclo (`python -m pipeline.run_etl`).

**Performance Goals**: ciclo completo das 4 fontes < 1 min no volume da PoC (SC-004:
40 veículos, ~2.400 eventos) — compatível com o ciclo de 1–2 min da demo.

**Constraints**:
- Idempotência de ponta a ponta: N execuções → mesmo estado consolidado **e** mesmo
  `log_qualidade` (transform processa só o lote da carga corrente — research R2).
- Rejeição nunca silenciosa: todo descarte vai a `log_qualidade` com motivo snake_case
  (vocabulário fechado no contrato — research R7).
- Isolamento por fonte: try/except por extrator; falha registrada, demais fontes seguem
  (constitution VI, SC-005).
- Rastreabilidade: `carga_em` + `fonte_origem` com identificação e hash do conteúdo em todo
  registro de staging (constitution II, research R1).
- Parametrização por ambiente: caminhos/URLs das fontes em variáveis de ambiente com defaults
  do repositório (constitution V; `.env.example` atualizado no mesmo MR).
- Camadas via banco: o pipeline não expõe API; o motor (004) e os painéis (005/006) só veem o
  resultado nas tabelas (constitution VI).

**Scale/Scope**: 4 extratores + cadastro base, ~10 regras de qualidade, 5 tabelas
consolidadas alvo de upsert; sem paralelismo (sequencial dá folga ao SC-004), sem
streaming/watchdog (decisão 3.2 da arquitetura: batch agendado).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Avaliação contra a constitution v1.0.1 (`.specify/memory/constitution.md`):

| Princípio | Status | Evidência / Nota |
|---|---|---|
| **I. Demo-crítico primeiro** | ✅ PASS | Spec 🔴 (tasks 4, 8, 9 da Fase 1). O extrator da pasta monitorada + carga idempotente são o caminho do disparo ao vivo: depositar CSV → ciclo ingere → motor cruza limiar. O plano prioriza US1→US3 (P1) antes de US4 (P2). |
| **II. Rastreabilidade total** | ✅ PASS | Staging bruto com `carga_em` + `fonte_origem` (arquivo\@hash / endpoint / aba XLSX em `aba_origem`); toda consolidada recebe `fonte_origem`; rejeição vai a `log_qualidade` com registro bruto + motivo (FR-002/FR-005). |
| **III. Dado inconsistente é requisito** | ✅ PASS | Todas as inconsistências catalogadas em `data/seeds/INCONSISTENCIAS.md` têm regra correspondente (normaliza ou rejeita com motivo — data-model § regras); linha inválida não derruba o lote (edge case "parcialmente corrompido"). |
| **IV. Conformidade (LGPD)** | ✅ PASS | `cnh`/`gravidade`/`codigo_infracao` são descartados estruturalmente na consolidação (FR-011; a tabela `multa` nem tem as colunas — contrato 002); staging retém o bruto como evidência auditável com expurgo documentado via `carga_em`. |
| **V. Parametrização como dados** | ✅ PASS | Nenhum limiar de negócio no pipeline (limiares são do motor via `limiar_config`); caminhos/URLs das fontes por env var com default. Mapeamentos de vocabulário são regra de qualidade dado→dado (não constante de negócio), documentados por FR-009 (research R6). |
| **VI. Camadas isoladas, idempotência** | ✅ PASS | Pipeline conversa só com o banco; upsert pelas chaves UNIQUE do contrato 002 (SC-001); detecção de novidade por hash torna a extração idempotente (R1); transform por lote não re-rejeita histórico (R2); try/except por fonte (SC-005). |
| **VII. Simplicidade, open source** | ✅ PASS | Sem framework de orquestração (batch sequencial simples — decisão D4/3.2); stack já existente (pandas/SQLAlchemy/httpx); estado de controle derivado do próprio staging, sem tabela nova (R1). |

**Gate result: PASS.** Nenhuma violação; sem itens para Complexity Tracking.

**Re-check pós-Phase 1: PASS** — o design manteve o esquema da spec 002 intacto (zero
migration nova). Únicas decisões fora do fluxo literal E→T→L, ambas documentadas: carga do
cadastro `veiculo` direto de `data/seeds/veiculos.json` sem staging (não é fonte legada
heterogênea — research R4) e novidade-por-hash embutida em `fonte_origem` (R1).

## Project Structure

### Documentation (this feature)

```text
specs/003-pipeline-etl/
├── spec.md              # Especificação (já existia)
├── plan.md              # Este arquivo (/speckit-plan)
├── research.md          # Phase 0: decisões técnicas R1–R10 (/speckit-plan)
├── data-model.md        # Phase 1: mapeamento staging→consolidado + regras de qualidade (/speckit-plan)
├── quickstart.md        # Phase 1: guia de validação executável (/speckit-plan)
├── contracts/
│   └── ciclo_pipeline.md    # Contrato do ciclo: entrada única, env vars, garantias, motivos de rejeição
└── tasks.md             # Phase 2 (/speckit-tasks — NÃO criado por /speckit-plan)
```

### Source Code (repository root)

Aderente à arquitetura v2 §9 (`pipeline/extract|transform|load` já existem vazios com
`.gitkeep`). Apenas arquivos desta spec:

```text
pipeline/
├── __init__.py
├── config.py                # env vars das fontes (inbox, URL da API, caminhos) com defaults
├── run_etl.py               # executar_ciclo(): orquestra E→T→L com isolamento por fonte; __main__
├── extract/
│   ├── __init__.py
│   ├── abastecimento.py     # varre data/inbox/ (CSVs novos por hash) → stg_abastecimento
│   ├── multas.py            # GET /multas (httpx, timeout) → stg_multas
│   ├── manutencao.py        # XLSX 3 abas → stg_manutencao (aba em aba_origem)
│   └── licenciamento.py     # SQLite legado (somente leitura) → stg_licenciamento
├── transform/
│   ├── __init__.py
│   ├── normalizadores.py    # placa (ADR-001), datas (3 formatos), decimais, vocabulários
│   └── qualidade.py         # aplica regras por fonte: separa válidos × rejeições com motivo
├── load/
│   ├── __init__.py
│   └── upsert.py            # upserts por dialeto + cadastro veiculo + km_atual + log_qualidade
└── README.md                # FR-009: regras de qualidade e origem de cada dado (task 10)

tests/
└── test_pipeline.py         # aceitação: US1–US4, SC-001..SC-005, FR-010/FR-011

.env.example                  # + variáveis do pipeline (PIPELINE_INBOX, MULTAS_API_URL, ...)
pyproject.toml                # httpx promovida do grupo dev para dependencies
```

**Structure Decision**: biblioteca única em `pipeline/` com os três estágios em subpacotes,
espelhando o fluxo da arquitetura §3.1 (papéis 🗂️ Dados em `extract/`+`transform/`, ⚙️ Backend
em `load/`). Acesso ao banco exclusivamente via `db.config.get_engine()`/`get_session()`
(contrato 002). `run_etl.py` expõe `executar_ciclo()` como função importável — o agendador da
spec 004 agenda a função, sem subprocess. Testes na suíte única `tests/`, padrão das specs
001/002.

## Complexity Tracking

> Nenhuma violação da constitution — tabela não aplicável. (Duas decisões que poderiam
> parecer desvio estão justificadas em research: R1 — estado de "arquivo já visto" derivado
> do próprio staging via hash em `fonte_origem`, em vez de tabela de controle nova que
> exigiria migration fora do escopo; R4 — cadastro `veiculo` carregado direto do JSON
> canônico sem staging, pois não é fonte legada heterogênea e criar `stg_veiculo` mudaria o
> contrato da spec 002 sem ganho.)
