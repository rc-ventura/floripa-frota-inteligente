# Tasks: Fontes de Dados Simuladas (Gerador de Dados)

**Input**: Design documents de `/specs/001-fontes-dados-simuladas/`

**Prerequisites**: plan.md, spec.md (clarificada 2026-07-14 + revisão de realismo ADRs 001–003), research.md (R1–R12), data-model.md, contracts/ (api_multas.md, formatos_arquivo.md), quickstart.md

**Tests**: INCLUÍDOS — exigência explícita do projeto (plan §Testing; kanban: "testes são critério de aceite"; constitution: não deixar para depois). Escrever cada teste ANTES da implementação da story e vê-lo falhar.

**Organization**: Tarefas agrupadas por user story, para implementação e teste independentes.

**Nota de paralelismo**: o gerador é um único arquivo (`data/gerador_dados.py`) e os testes vivem em um único `tests/test_gerador_dados.py` (decisão do plan §Structure). Tarefas que editam o mesmo arquivo NÃO levam `[P]`, mesmo quando logicamente independentes — o paralelismo real está entre gerador × API × docs × seeds.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US4)
- Caminhos exatos de arquivo em cada descrição

## Path Conventions

Projeto single (raiz do repositório), conforme plan.md e arquitetura v2 §9:
`data/gerador_dados.py` (CLI), `data/seeds/` (saídas), `data/inbox/` (pasta monitorada),
`fake_api/` (mini-API), `tests/` (pytest), `pyproject.toml` (raiz).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Projeto Python inicializado com dependências e esqueleto de pastas

- [X] T001 Criar `pyproject.toml` na raiz com dependências `pandas>=2.2`, `openpyxl>=3.1`, `fastapi>=0.110`, `uvicorn>=0.30`, `numpy>=1.26` e dev `pytest>=8.0`, `httpx>=0.27`, com gestor `uv` (lockfile versionado) e configuração do pytest (research R9)
- [X] T002 [P] Criar esqueleto de diretórios e versionamento: `data/seeds/` (vazia), `data/inbox/.gitkeep`, `fake_api/`, `tests/`; adicionar regra no `.gitignore` para não versionar conteúdo de `data/inbox/` (mantendo o `.gitkeep`)
- [X] T003 [P] Criar `tests/test_gerador_dados.py` com fixtures base: fixture de sessão que executa o gerador em diretório temporário (`--output`) e fixtures de leitura dos artefatos (CSV via pandas, JSON, XLSX via openpyxl, SQLite via sqlite3)

**Checkpoint**: `uv sync` funciona; `pytest` coleta 0 testes sem erro

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Núcleo do gerador do qual TODAS as stories dependem: CLI determinístico, parâmetros de calibração, cadastro base e série de hodômetro

**⚠️ CRITICAL**: nenhuma story pode começar antes desta fase terminar

- [X] T004 Implementar esqueleto CLI de `data/gerador_dados.py`: `argparse` com `--output` (default: raiz do repo) e `--data-ancora` (data ISO; default `2026-07-15`, documentado — é a referência de TODAS as datas relativas: dias_desde_ultima, vencimentos, janela de 8 meses; nunca `datetime.now()`), `SEED = 42` e um único `numpy.random.default_rng(SEED)` injetado como argumento em toda função de geração — nenhuma outra fonte de entropia (research R1, FR-006)
- [X] T005 Definir os parâmetros de calibração como constantes de geração em `data/gerador_dados.py` (bloco único, justificado no Complexity Tracking do plan): faixas por tipo de veículo (km/mês, km/L, tanque — research R12), valores de multa por gravidade e distribuição (R10), calendário DETRAN-SC por final de placa (R11), proporção de placas Mercosul/antigo 70/30 (R7, ADR-001), catálogo de marcas/modelos por tipo e razão de custo corretiva/preventiva 3–5× (R13) — os marcos de revisão programada NÃO são redeclarados: reutilizam as linhas `revisao_geral` da tabela-semente (T006, fonte única)
- [X] T006 Implementar `gerar_limiares_semente()` em `data/gerador_dados.py` escrevendo `data/seeds/limiares_semente.json` com as 9 linhas da tabela-semente (Clarifications 2026-07-14 — espelho literal da futura `LIMIAR_CONFIG` da spec 002)
- [X] T007 Implementar `gerar_veiculos()` em `data/gerador_dados.py` escrevendo `data/seeds/veiculos.json`: 40 veículos (≈30 leves, 6 ambulâncias, 4 caminhões), placas únicas nos dois formatos validadas por `^[A-Z]{3}\d[A-Z\d]\d{2}$` (~70% Mercosul — R7), marca/modelo do catálogo real por tipo com `ano` ~2015–2026 e `em_garantia=true` quando ano ≥ 2023 (~25% da frota — R13, FR-012), `secretaria` sintética, `km_mes` sorteado na faixa do tipo (R12), flags `demo_gatilho`/`demo_gatilho_tipo` nos índices 0 e 1 (R4) e `custo_desproporcional=true` em exatamente 1 leve fora da demo (FR-009)
- [X] T008 Implementar em `data/gerador_dados.py` a série de hodômetro por veículo (`gerar_serie_hodometro()`): leituras mensais monotônicas crescentes ao longo de 8 meses derivadas de `km_mes` (R12, FR-011) e o pool de condutores sintéticos `COND-NNN` por veículo (FR-004)

**Checkpoint**: `python data/gerador_dados.py` roda sem erro e produz `veiculos.json` + `limiares_semente.json` reproduzíveis

---

## Phase 3: User Story 1 — Quatro fontes heterogêneas prontas para o pipeline (Priority: P1) 🎯 MVP

**Goal**: Um comando produz as 4 fontes (CSV, JSON via API, XLSX multi-abas, SQLite), todas referenciando o mesmo cadastro de veículos, e a mini-API FastAPI serve as multas.

**Independent Test**: executar o gerador em um único comando e verificar que os 4 artefatos existem nos locais do plan, cada um no seu formato, referenciando o mesmo conjunto de placas (quickstart Cenário 1).

### Tests for User Story 1 (escrever primeiro — devem falhar)

- [X] T009 [US1] Escrever `test_artefatos_existem` em `tests/test_gerador_dados.py`: após 1 execução existem `data/seeds/abastecimento.csv`, `fake_api/multas.json`, `data/seeds/manutencao.xlsx` (3 abas), `data/seeds/licenciamento.sqlite`, `data/seeds/veiculos.json` e `data/seeds/limiares_semente.json` (FR-001, FR-007)
- [X] T010 [US1] Escrever `test_mesmo_conjunto_veiculos` em `tests/test_gerador_dados.py`: placas de todas as fontes, após normalização (upper + strip de hífen/espaço), pertencem ao cadastro de `veiculos.json` (FR-002; aceita os dois formatos — ADR-001)
- [X] T011 [US1] Escrever `test_endpoint_multas` em `tests/test_gerador_dados.py` com `fastapi.testclient.TestClient`: `GET /multas` → 200 com lista JSON no schema de `contracts/api_multas.md`; `GET /multas/{placa}` filtra em minúsculas; `GET /health` → `{"status":"ok"}` (FR-008)

### Implementation for User Story 1

- [X] T012 [US1] Implementar `gerar_abastecimento()` em `data/gerador_dados.py` → `data/seeds/abastecimento.csv` conforme `contracts/formatos_arquivo.md`: colunas `placa,data,litros,valor,condutor,km`; frequência e litros derivados da série de hodômetro ÷ consumo do veículo (R12); ~1.500 registros; consumo no piso da faixa para o veículo `custo_desproporcional` (FR-009)
- [X] T013 [US1] Implementar `gerar_manutencao()` em `data/gerador_dados.py` → `data/seeds/manutencao.xlsx` com 3 abas (`Oficina Central`, `Oficina Regional Norte`, `Manutenção Terceirizada`) via `pandas.ExcelWriter(engine="openpyxl")` (R3); coluna `categoria` preventiva/corretiva com corretivas a 3–5× o valor médio das preventivas (R13, FR-013); cadência derivada dos limiares-semente × km/mês; veículos `em_garantia` com revisões programadas nos marcos do fabricante na aba `Manutenção Terceirizada` (grafias "Revisão 10.000 km" — R13); `km_no_momento` interpolado da mesma série de hodômetro (R12); 2–3 corretivas extras de valor alto no veículo caro (FR-009); ~300 registros
- [X] T014 [US1] Implementar `gerar_multas()` em `data/gerador_dados.py` → `fake_api/multas.json`: gravidade sorteada → `valor` da tabela CTB com multiplicadores (R10), `codigo_infracao`, `situacao`, `cnh` sintética com DV calculado e perturbado (R2), distribuição enviesada por veículo/condutor concentrada no veículo caro (R10/R12); ~100 registros
- [X] T015 [US1] Implementar `gerar_licenciamento()` em `data/gerador_dados.py` → `data/seeds/licenciamento.sqlite` via `sqlite3` stdlib (R6): tabela `licenciamento` sem PRIMARY KEY, `vencimento` coerente com o final da placa (calendário DETRAN-SC — R11), ≥2 registros vencidos e ≥2 vencendo em ≤7 dias fora dos veículos da demo (FR-010)
- [X] T016 [US1] Ligar todos os passos na orquestração do CLI em `data/gerador_dados.py`: um comando gera tudo, apagando/recriando as saídas (mesma semente → mesmo estado); cronometrar < 1 min (FR-001, FR-007, SC-001)
- [X] T017 [P] [US1] Implementar `fake_api/main.py` (FastAPI, ~20 linhas — R5, D5): carrega `multas.json` uma vez no startup; `GET /multas`, `GET /multas/{placa}` (comparação em minúsculas), `GET /health`; porta via `FAKE_API_PORT` (default 8000)
- [X] T018 [P] [US1] Escrever `fake_api/README.md`: como subir (`uvicorn fake_api.main:app --port 8000`), endpoints e referência ao contrato `specs/001-fontes-dados-simuladas/contracts/api_multas.md`

**Checkpoint**: US1 completa — 4 fontes geradas + API respondendo; T009–T011 verdes

---

## Phase 4: User Story 2 — Inconsistências propositais documentadas (Priority: P1)

**Goal**: Cada fonte carrega as inconsistências da arquitetura §2, e `INCONSISTENCIAS.md` documenta cada uma com exemplo real extraído dos dados.

**Independent Test**: inspecionar cada dataset e conferir, item a item, a lista de `data/seeds/INCONSISTENCIAS.md` (quickstart Cenário 3).

### Tests for User Story 2 (escrever primeiro — devem falhar)

- [X] T019 [US2] Escrever `test_inconsistencias` em `tests/test_gerador_dados.py` (checklist programático — SC-002): CSV com ~50% placas com hífen, 2 formatos de data e vírgula decimal; multas com placas 100% minúsculas; XLSX com ~15% de km ausente e ≥3 grafias de tipo; SQLite com placas duplicadas e 3 formatos de vencimento; e `data/seeds/INCONSISTENCIAS.md` existente listando todas

### Implementation for User Story 2

- [X] T020 [US2] Injetar inconsistências no CSV em `gerar_abastecimento()` (`data/gerador_dados.py`): ~50% das placas com hífen, datas alternando `dd/mm/aaaa` e `aaaa-mm-dd`, `litros`/`valor` com vírgula decimal (R7, arquitetura v2 §2) — sem invalidar os registros dos 2 veículos da demo (edge case da spec)
- [X] T021 [US2] Injetar inconsistências nas multas em `gerar_multas()` (`data/gerador_dados.py`): placas em minúsculas, sem hífen (R7); manter `cnh` presente como evidência do desafio LGPD (descartada pelo pipeline — spec 003 FR-011)
- [X] T022 [US2] Injetar inconsistências na manutenção em `gerar_manutencao()` (`data/gerador_dados.py`): `tipo` em texto livre (`troca de oleo`, `Troca Óleo`, `TROCA_OLEO`, `Revisão 10.000 km`), `categoria` com grafias variadas (`Preventiva`, `CORRETIVA`, `prev.` — R13), `data` misturando TEXT e serial Excel, `km_no_momento` ausente em ~15% — nunca nos registros-âncora (última `troca_oleo`) dos veículos da demo
- [X] T023 [US2] Injetar inconsistências no licenciamento em `gerar_licenciamento()` (`data/gerador_dados.py`): ~20% de placas com 2 registros (vencimento antigo + atual) e `vencimento` em 3 formatos (`dd/mm/aaaa` TEXT, `aaaa-mm-dd` TEXT, serial Excel INTEGER — R6)
- [X] T024 [US2] Implementar `gerar_inconsistencias_md()` em `data/gerador_dados.py` → `data/seeds/INCONSISTENCIAS.md`: tabela por fonte → inconsistência → exemplo concreto extraído dos dados gerados → regra de qualidade que trata (spec 003) → motivo de rejeição esperado em `log_qualidade` (R8, FR-003)

**Checkpoint**: US1 e US2 verdes — fontes heterogêneas E documentadas

---

## Phase 5: User Story 3 — Cenário determinístico da demo (Priority: P2)

**Goal**: Veículo A a ~600 km do limite de km (antecedência não cruzada — gatilho ao vivo) e veículo B a 166 dias (antecedência de tempo já cruzada — alerta no 1º ciclo do motor), CSV-gatilho pronto, e regeneração 100% reproduzível.

**Independent Test**: regenerar N vezes e confirmar os mesmos 2 veículos às mesmas distâncias; conferir que o gatilho cruza o limiar de antecedência (quickstart Cenários 2 e 5).

### Tests for User Story 3 (escrever primeiro — devem falhar)

- [X] T025 [US3] Escrever `test_cenario_demo` em `tests/test_gerador_dados.py`: veículo índice 0 (`demo_gatilho_tipo="km"`) com `km_atual − km_no_momento(última troca_oleo) = 4400`; veículo índice 1 (`"tempo"`) com última `troca_oleo` há 166 dias; `gatilho_demo_abastecimento.csv` com 1 registro do veículo A cujo `km` ≥ 4501 (FR-005, R4)
- [X] T026 [US3] Escrever `test_determinismo` em `tests/test_gerador_dados.py`: 2 execuções em diretórios temporários → checksums SHA-256 idênticos por arquivo, para TODOS os artefatos (R1, FR-006, SC-004)

### Implementation for User Story 3

- [X] T027 [US3] Posicionar deterministicamente os veículos da demo em `data/gerador_dados.py` (valores literais, não sorteados — R4): A = índice 0, leve, última `troca_oleo` com `km_no_momento = km_atual − 4400` (faltam 600 para o limite 5000; antecedência dispara a 4500); B = índice 1, leve, última `troca_oleo` datada 166 dias antes da data-âncora (cruzou a antecedência 165, não o limite 180 — dispara no 1º ciclo do motor)
- [X] T028 [US3] Garantir em `data/gerador_dados.py` que os demais 38 veículos ficam longe dos limiares (`km_desde_ultima` e `dias_desde_ultima` bem dentro dos limites — sem alertas espúrios) e que os registros-âncora dos veículos da demo passam pelas regras de qualidade (placa válida, data válida, km presente — edge case da spec)
- [X] T029 [US3] Implementar `gerar_gatilho_demo()` em `data/gerador_dados.py` → `data/seeds/gatilho_demo_abastecimento.csv`: mesmo contrato do CSV de abastecimento, 1 registro do veículo A com `km` que eleva `km_atual` a ≥ 4501 (FR-005); documentar no cabeçalho do arquivo gerado que ele é depositado em `data/inbox/` durante a demo

**Checkpoint**: cenário da demo reproduzível — T025 e T026 verdes em 10 regenerações

---

## Phase 6: User Story 4 — Nenhum dado pessoal real (Priority: P2)

**Goal**: Pseudonimização de origem comprovada por varredura: só `COND-NNN`, CNHs 100% estruturalmente inválidas, zero nome/CPF/matrícula.

**Independent Test**: varrer todos os datasets gerados buscando qualquer campo de identificação pessoal em claro (quickstart Cenário 4).

### Tests for User Story 4 (escrever primeiro — devem falhar)

- [X] T030 [US4] Escrever `test_lgpd_sem_dado_pessoal` em `tests/test_gerador_dados.py`: varredura de TODOS os artefatos gerados — campos de condutor casam `^COND-\d{3}$` em 100% das ocorrências; nenhum padrão de CPF válido; validador módulo 11 confirma que 100% das `cnh` têm DV inválido (R2, FR-004, SC-003)

### Implementation for User Story 4

- [X] T031 [US4] Revisar/ajustar em `data/gerador_dados.py` os helpers de dado pessoal sintético até T030 passar: `cnh_sintetica()` calcula o DV correto (módulo 11, Resolução CONTRAN 886/2021) e o perturba (`(dv+1) % 10` — R2); pool de condutores exclusivamente `COND-NNN` em abastecimento e multas; nenhum campo de nome/CPF/matrícula em nenhuma fonte (FR-004)

**Checkpoint**: todas as stories verdes de forma independente

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Coerência física transversal (ADR-003), seeds versionados e validação do quickstart

- [X] T032 Escrever `test_coerencia_fisica` em `tests/test_gerador_dados.py` (FR-011, FR-012, FR-013, SC-005, SC-006 — transversal às fontes): hodômetro monotônico por veículo cruzando CSV × XLSX (exceto anomalias listadas em `INCONSISTENCIAS.md`); km/L derivado dentro das faixas por tipo (leve 8–14, ambulância 6–10, caminhão 2–5); 100% dos valores de multa ∈ tabela CTB; vencimento coerente com o final da placa; exatamente 1 veículo `custo_desproporcional`; ~70% de placas Mercosul; 100% dos veículos `em_garantia` com revisão programada dentro do marco vigente; razão de custo médio corretiva ÷ preventiva entre 3× e 5×
- [X] T033 Executar o gerador na raiz e versionar os artefatos iniciais (`data/seeds/*.json`, `*.csv`, `*.xlsx`, `*.sqlite`, `INCONSISTENCIAS.md` e `fake_api/multas.json` — FR-007), medindo SC-001 com `time python data/gerador_dados.py` (< 1 min)
- [X] T034 Validar `specs/001-fontes-dados-simuladas/quickstart.md` de ponta a ponta (Cenários 1–8) em máquina limpa e corrigir divergências de docs/comandos encontradas (evidência manual de SC-002 — checklist de inconsistências — e FR-007 — artefatos nos locais convencionados)
- [X] T035 [P] Rodar a suíte completa (`pytest tests/test_gerador_dados.py -v`) 10 vezes consecutivas confirmando SC-004 e revisar o código do gerador (nomes em português de domínio, funções puras recebendo `rng`, zero constante de negócio fora do bloco de parâmetros — constitution V/VII)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — BLOQUEIA todas as stories (cadastro + série de hodômetro + parâmetros são insumo de todas as fontes)
- **User Stories (Phases 3–6)**: todas dependem da Phase 2
  - US2 edita as funções criadas na US1 (mesmo arquivo `data/gerador_dados.py`) → na prática US1 → US2 em sequência
  - US3 e US4 tocam pontos distintos do gerador; podem seguir US1 diretamente, mas US3 depende de `gerar_manutencao()` (T013) e US4 de `gerar_multas()` (T014)
- **Polish (Phase 7)**: depende de todas as stories

### User Story Dependencies

- **US1 (P1)**: só Foundational — é o MVP
- **US2 (P1)**: injeta inconsistências nas funções da US1 (T012–T015)
- **US3 (P2)**: depende de T007 (flags no cadastro) e T013 (manutenção); independente de US2/US4 para teste
- **US4 (P2)**: depende de T012/T014 (onde condutor/cnh aparecem); independente de US2/US3 para teste

### Within Each User Story

- Teste primeiro (deve falhar) → implementação → teste verde
- Cadastro/série (Foundational) → fontes → orquestração → API/docs

### Parallel Opportunities

- Phase 1: T002 ∥ T003 (após T001)
- US1: T017 (fake_api/main.py) e T018 (fake_api/README.md) ∥ entre si e ∥ T012–T016 (arquivos diferentes); T009–T011 são sequenciais entre si (mesmo arquivo de teste), mas ∥ com T017/T018
- Com 2 pessoas: uma no gerador (T012→T016), outra na API + testes (T009–T011, T017–T018)
- US3 ∥ US4 após US1 (funções-alvo distintas; combinar merges no mesmo arquivo)

---

## Parallel Example: User Story 1

```bash
# Dev A — gerador (sequencial, mesmo arquivo):
Task: "T012 gerar_abastecimento() em data/gerador_dados.py"
Task: "T013 gerar_manutencao() em data/gerador_dados.py"
Task: "T014 gerar_multas() em data/gerador_dados.py"
Task: "T015 gerar_licenciamento() em data/gerador_dados.py"
Task: "T016 orquestração do CLI"

# Dev B — em paralelo (arquivos diferentes):
Task: "T009–T011 testes em tests/test_gerador_dados.py"
Task: "T017 FastAPI em fake_api/main.py"
Task: "T018 fake_api/README.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational)
2. Phase 3 (US1): 4 fontes + API — **MVP que destrava specs 002/003 e todo o time**
3. **PARAR e VALIDAR**: quickstart Cenário 1 + Cenário 6
4. Seguir para US2 (inconsistências) — sem ela a spec 003 não tem o que tratar

### Incremental Delivery

1. Setup + Foundational → gerador roda e produz cadastro
2. US1 → 4 fontes + API → **demo interna: `python data/gerador_dados.py` + `curl /multas`**
3. US2 → inconsistências + `INCONSISTENCIAS.md` → pipeline (spec 003) pode começar as regras de qualidade
4. US3 → cenário da demo + gatilho → motor (spec 004) pode ensaiar o disparo
5. US4 → varredura LGPD verde → evidência de conformidade para a banca
6. Polish → coerência física + seeds versionados + quickstart validado

### Caminho demo-crítico (constitution I)

`T001→T008` → US1 (`T012,T013,T016`) → US3 (`T025–T029`) é o caminho mínimo até o CSV-gatilho existir; não deixar US3 para o fim se o ensaio da demo (spec 007) estiver próximo.

---

## Notes

- Tarefas `[P]` = arquivos diferentes, sem dependência pendente; o gerador é um arquivo único — respeitar a sequência dentro dele
- Todo valor de calibração (faixas, tabela CTB, calendário, 70/30) vive no bloco de parâmetros de T005 — são dados de geração da fonte simulada, não regra de negócio do motor (constitution V; ADR-003)
- Commit após cada tarefa ou grupo lógico; mensagens em português no imperativo (`feat:`, `test:`, `docs:`)
- Cada checkpoint é um ponto de validação independente da story — parar e rodar o teste da story antes de seguir
