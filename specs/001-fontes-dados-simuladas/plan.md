# Implementation Plan: Fontes de Dados Simuladas (Gerador de Dados)

**Branch**: `feature/001-fontes-dados-simuladas` | **Date**: 2026-07-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fontes-dados-simuladas/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Gerar 4 datasets simulados heterogêneos (abastecimento CSV, multas JSON via mini-API FastAPI,
manutenção XLSX multi-abas, licenciamento SQLite) com inconsistências propositais documentadas,
pseudonimização LGPD desde a origem (`COND-NNN`), cenário determinístico da demo (veículo A a
~600 km do limite de km — gatilho ao vivo; veículo B a 166 dias — antecedência de tempo já
cruzada, alerta no 1º ciclo; limiares `troca_oleo`/`leve` = 5000 km / 180 dias) e um CSV-gatilho
pronto para depositar ao vivo. Stack: Python 3.12 + pandas + openpyxl + FastAPI, conforme
decisões D1 e D5 da arquitetura v2.0. Revisão de realismo de 2026-07-14 (ADRs 001–003):
placas nos dois formatos vigentes (~70% Mercosul), km do hodômetro persistido no consolidado,
multas com valores tabelados do CTB, licenciamento pelo final da placa, modelo de consumo
coerente e um veículo deliberadamente caro para a spec 006. É o ponto de partida do projeto
(nenhuma dependência) e destrava todas as demais frentes (pipeline, motor, dashboard).

## Technical Context

**Language/Version**: Python 3.12 (decisão D1 da arquitetura v1.0).

**Primary Dependencies**:
- `pandas` — manipulação tabular, escrita de CSV e leitura/escrita de Excel.
- `openpyxl` — escrita de XLSX multi-abas (engine do pandas para `.xlsx`).
- `fastapi` + `uvicorn` — mini-API que serve as multas em JSON (decisão D5).
- `numpy` — gerador de números aleatórios com semente fixa (determinismo, FR-006).
- `Faker` (opcional, avaliar em research.md) — geração de nomes sintéticos de modelos/marcas; se usado, semente fixa.

**Storage**: Arquivos locais (não há banco nesta spec):
- `data/seeds/abastecimento.csv` — CSV de abastecimento (carga histórica inicial).
- `data/seeds/manutencao.xlsx` — XLSX multi-abas de manutenção.
- `data/seeds/licenciamento.sqlite` — base SQLite de licenciamento.
- `data/seeds/veiculos.json` — cadastro canônico de veículos (referência interna do gerador; NÃO é uma das 4 fontes legadas, é o cadastro base que as 4 fontes espelham com grafias divergentes).
- `data/seeds/limiares_semente.json` — tabela-semente de limiares usada para posicionar os veículos da demo (espelha os valores que a spec 002 formalizará em `LIMIAR_CONFIG`).
- `data/seeds/gatilho_demo_abastecimento.csv` — CSV-gatilho da demo (depositado em `data/inbox/` durante a apresentação).
- `fake_api/multas.json` — payload JSON servido pela FastAPI (gerado pelo `gerador_dados.py`).
- `fake_api/main.py` — app FastAPI que lê `multas.json` e expõe endpoint GET.

**Testing**: `pytest` (mesma stack do projeto; testes de aceitação em `tests/test_gerador_dados.py`):
- Teste de determinismo (rodar 2x → outputs idênticos, SC-004).
- Teste LGPD (varredura por nomes/CPFs/CNHs reais → zero ocorrências, SC-003).
- Teste de inconsistências (checklist programático por fonte, SC-002).
- Teste dos 4 artefatos existem nos locais convencionados (FR-001, FR-007).
- Teste do cenário da demo (2 veículos à distância esperada dos limiares, FR-005).
- Teste do endpoint FastAPI (GET retorna JSON válido, FR-008).

**Target Platform**: Local (dev/demo); compatível com Docker Compose (decisão D6, empacotamento na spec 007). Python 3.12 em qualquer máquina da equipe (SC-001: geração < 1 min).

**Project Type**: CLI (gerador de dados) + web-service mínimo (FastAPI fake de multas).

**Performance Goals**: Geração dos 4 datasets em < 1 min em máquina comum (SC-001). Mini-API responde GET em < 100 ms localmente.

**Constraints**:
- Determinismo absoluto: mesmas entradas (semente fixa + data-âncora explícita) → mesmos dados (FR-006, SC-004). Nenhuma fonte de entropia externa (sem `os.urandom`, sem `datetime.now()`); toda data relativa deriva de `DATA_ANCORA` (CLI `--data-ancora`, default documentado — regenerar seeds com a âncora do dia da apresentação faz parte do roteiro da demo, spec 007).
- Zero dado pessoal real (FR-004, SC-003, constitution IV).
- Os 2 veículos da demo devem passar pelas regras de qualidade do pipeline (Edge Case da spec) — logo, suas placas são válidas no formato canônico, apenas as *demais* fontes as grafam de forma divergente.
- Coerência física (FR-011, SC-005, ADR-003): hodômetro monotônico por veículo e consistente entre fontes; litros derivados do modelo de consumo por tipo (research R12); valores de multa ∈ tabela de gravidades do CTB (R10); vencimento de licenciamento pelo final da placa (R11).

**Scale/Scope**: 40 veículos (≈30 leves, 6 ambulâncias, 4 caminhões) × 8 meses de histórico (decisão 2026-07-14). Volume estimado pelo modelo de consumo (research R12): ~1.500 abastecimentos, ~300 manutenções, ~100 multas (distribuição enviesada), 40+ registros de licenciamento (inclui duplicatas propositais). Suficiente para o painel de custos agregar; pequeno o bastante para a demo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Avaliação dos princípios I–VII da constitution (`.specify/memory/constitution.md` v1.0.0):

| Princípio | Status | Evidência / Nota |
|---|---|---|
| **I. Demo-crítico primeiro** | ✅ PASS | Esta spec É demo-crítica: gera os 2 veículos do gatilho e o CSV-gatilho da demo (FR-005, US3). É o ponto de partida do caminho crítico `001 → 003 → 004 → 005 → 007`. |
| **II. Rastreabilidade total da origem** | ✅ PASS (com nota) | O gerador produz arquivos nomeados e versionados (cada fonte tem path fixo em `data/seeds/`); a rastreabilidade no sentido de `fonte_origem` + carimbo de carga é responsabilidade do pipeline (spec 003) ao ingerir. O gerador garante que cada arquivo é identificável e estável (semente fixa → checksums reproduzíveis). |
| **III. Dado inconsistente é requisito** | ✅ PASS | Esta spec **encarna** o princípio: gera as inconsistências propositais da arquitetura §2 (FR-003, US2). As inconsistências são documentadas em `data/seeds/INCONSISTENCIAS.md` (artefato desta spec). |
| **IV. Conformidade desde a concepção (LGPD)** | ✅ PASS | Pseudonimização na origem: `COND-NNN` em todas as fontes (FR-004). CNH sintética não-real nas multas, descartada pelo pipeline na carga (clarificação 2026-07-14). Nenhum nome/CPF/CNH real. Teste de varredura SC-003. |
| **V. Parametrização como dados** | ✅ PASS (com nota — ver Complexity Tracking) | Os limiares runtime vivem em `LIMIAR_CONFIG` (spec 002). O gerador usa uma `LIMIARES_SEMENTE` local (em `limiares_semente.json`) para posicionar os veículos da demo — é um parâmetro de *geração*, não uma constante de negócio do motor. A spec 002 formalizará os mesmos valores em `LIMIAR_CONFIG`. Ver Complexity Tracking para a justificativa. |
| **VI. Camadas isoladas, idempotência** | ✅ PASS | O gerador não cruza camadas: produz arquivos, não lê/escreve banco. Idempotente por design (semente fixa → N execuções → mesmo estado, FR-006, SC-004). |
| **VII. Simplicidade, open source, sem lock-in** | ✅ PASS | Stack 100% open source (Python, pandas, openpyxl, FastAPI, numpy). Sem hardware, sem serviços proprietários. Solução simples: um script + uma mini-API. |

**Gate result: PASS.** Nenhuma violação injustificada. Um item de nota no princípio V (gerador tem cópia local dos limiares para posicionamento) — justificado em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-fontes-dados-simuladas/
├── spec.md              # Especificação (o quê + porquê) — já existia, clarificada 2026-07-14
├── plan.md              # Este arquivo (plano técnico, /speckit-plan)
├── research.md          # Phase 0: resolução de unknowns (/speckit-plan)
├── data-model.md        # Phase 1: shape das 4 fontes simuladas + cadastro base (/speckit-plan)
├── quickstart.md        # Phase 1: guia de validação executável (/speckit-plan)
├── contracts/
│   ├── api_multas.md    # Contrato do endpoint FastAPI (GET /multas)
│   └── formatos_arquivo.md  # Contratos de formato: CSV, XLSX, SQLite
└── tasks.md             # Phase 2: passo a passo (/speckit-tasks — NÃO criado por /speckit-plan)
```

### Source Code (repository root)

Estrutura aderente à seção 9 da arquitetura v1.0. Apenas os arquivos desta spec; demais pastas
(`pipeline/`, `alertas/`, `db/`, `dashboard/`) pertencem a outras specs e não são tocadas aqui.

```text
data/
├── gerador_dados.py          # CLI: gera os 4 datasets + cadastro base + gatilho da demo (1 comando)
├── seeds/
│   ├── INCONSISTENCIAS.md    # Documentação das inconsistências propositais por fonte (FR-003)
│   ├── veiculos.json         # Cadastro canônico de 40 veículos (referência interna do gerador)
│   ├── limiares_semente.json # Tabela-semente de 9 linhas (espelha LIMIAR_CONFIG da spec 002)
│   ├── abastecimento.csv     # Fonte 1: abastecimento (com coluna km/hodômetro)
│   ├── manutencao.xlsx       # Fonte 3: manutenção multi-abas
│   ├── licenciamento.sqlite  # Fonte 4: licenciamento
│   └── gatilho_demo_abastecimento.csv  # CSV-gatilho da demo (depositado em inbox/ na apresentação)
└── inbox/
    └── .gitkeep              # Pasta monitorada; conteúdo não versionado (.gitignore)

fake_api/
├── main.py                   # FastAPI: GET /multas serve o JSON gerado
├── multas.json               # Payload gerado pelo gerador_dados.py (Fonte 2)
└── README.md                 # Como subir a API (uvicorn fake_api.main:app)

tests/
└── test_gerador_dados.py     # Testes de aceitação (determinismo, LGPD, inconsistências, demo)

pyproject.toml                # Dependências do projeto (poetry/uv) — criado nesta spec se não existir
```

**Structure Decision**: Estrutura "single project" simplificada, aderente à seção 9 da arquitetura.
O gerador é um CLI (`data/gerador_dados.py`) que escreve em `data/seeds/` e `fake_api/`; a mini-API
é um módulo FastAPI isolado em `fake_api/`. Não há separação backend/frontend (esta spec não tem
frontend). Testes em `tests/` na raiz, seguindo o padrão `pytest` do projeto.

## Complexity Tracking

> **Preenchido porque o Constitution Check tem uma nota (não violação) no princípio V que merece justificativa.**

| Item | Por que necessário | Alternativa mais simples rejeitada porque |
|---|---|---|
| `LIMIARES_SEMENTE` local no gerador (cópia dos valores que serão formalizados em `LIMIAR_CONFIG` pela spec 002) | O gerador precisa dos limiares para posicionar os 2 veículos da demo (~600 km / 166 dias contra o limite). O gerador roda **antes** do banco existir (é a fonte de dados; não pode depender da `LIMIAR_CONFIG` que vive no banco). | Ler `LIMIAR_CONFIG` do banco no gerador: rejeitado porque cria dependência circular (gerador → banco → gerador) e viola o isolamento de camadas (constitution VI — o gerador é camada de fonte, não pode ler o banco de armazenamento). A sincronização é garantida por convenção: `limiares_semente.json` e a migration da spec 002 usam os mesmos valores literais, e o `INCONSISTENCIAS.md`/quickstart documentam o acoplamento. |
| Bloco de constantes de calibração no gerador (tabela CTB de multas, calendário DETRAN-SC, faixas km/mês·km/L·tanque, catálogo de marcas/modelos, proporção 70/30 de placas, razão corretiva/preventiva 3–5×, marcos de revisão — T005) | São a **definição da fonte simulada** (fixture), não regra de negócio do sistema: o motor, o pipeline e o dashboard nunca leem esses valores — eles só existem para os arquivos-fonte nascerem plausíveis (ADR-003). A constitution V mira limiares do motor (`LIMIAR_CONFIG`) e parâmetros operacionais (variáveis de ambiente), ambos atendidos. | Externalizar em `calibracao.json`: rejeitado — adicionaria um artefato de configuração para valores que nunca mudam em runtime nem são consumidos por outra camada, violando simplicidade (constitution VII). Se um valor regulatório mudar (CTB, calendário), edita-se o bloco único de T005 e regenera-se — mesmo custo de editar um JSON. Os marcos de revisão programada reutilizam as linhas `revisao_geral` da `limiares_semente.json` (fonte única, sem duplicação). |
