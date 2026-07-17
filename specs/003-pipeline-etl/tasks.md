# Tasks: Pipeline ETL de Integração das Fontes

**Input**: Design documents from `/specs/003-pipeline-etl/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R10), data-model.md, contracts/ciclo_pipeline.md

**Tests**: INCLUÍDOS — a spec exige comprovação por teste automatizado (FR-006, SC-001..SC-005)
e a constitution trata testes como critério de aceite do kanban ("idempotência da carga — não
deixe para depois").

**Organization**: tasks agrupadas por user story (US1 extração · US2 qualidade · US3
idempotência · US4 resiliência), nas prioridades da spec (P1, P1, P1, P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: paralelizável (arquivos distintos, sem dependência de task incompleta)
- **[Story]**: US1..US4 (mapeia para as user stories da spec.md)

## Path Conventions

Projeto único na raiz do repositório (plan.md § Project Structure): código em `pipeline/`,
testes na suíte única `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: estrutura de pacotes, dependência e parametrização — pré-condição de tudo.

- [ ] T001 Criar esqueleto de pacotes: `pipeline/__init__.py`, `pipeline/extract/__init__.py`, `pipeline/transform/__init__.py`, `pipeline/load/__init__.py` (dirs já existem com `.gitkeep`)
- [ ] T002 Promover `httpx>=0.27` do grupo `dev` para `dependencies` em `pyproject.toml` + `uv lock` (research R9)
- [ ] T003 [P] Criar `pipeline/config.py` — env vars do contrato com defaults: `PIPELINE_INBOX`, `MULTAS_API_URL`, `PIPELINE_XLSX_MANUTENCAO`, `PIPELINE_SQLITE_LICENCIAMENTO`, `PIPELINE_CADASTRO_VEICULOS` (contracts/ciclo_pipeline.md § Configuração; constitution V)
- [ ] T004 [P] Adicionar as 5 variáveis do pipeline (comentadas, com defaults) em `.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: normalizadores, helpers de novidade/lote, base de upsert e cadastro — TODAS as
user stories dependem disto.

**⚠️ CRITICAL**: nenhuma user story começa antes desta fase terminar.

- [ ] T005 Criar `pipeline/transform/normalizadores.py` — `normalizar_placa()` (upper, sem hífen/espaço, valida `db.models.REGEX_PLACA_CANONICA` — ADR-001), `interpretar_data()` (dd/mm/aaaa → ISO → serial Excel 20.000–80.000 origem 1899-12-30 — R5), `converter_decimal()` (vírgula→ponto), `normalizar_tipo_manutencao()`/`normalizar_categoria()`/`normalizar_situacao()` (radicais + sem acento — R6)
- [ ] T006 [P] Criar helpers de novidade e lote em `pipeline/extract/__init__.py` — `sha256_conteudo()`, `montar_fonte_origem(identificador, hash)` (`id@sha256:12hex`), `fonte_ja_vista(engine, tabela_stg, hash)` via LIKE no staging, `novo_lote()` (carga_em único por fonte/ciclo) (R1/R2)
- [ ] T007 [P] Criar base de carga em `pipeline/load/upsert.py` — fábrica de INSERT por dialeto (`sqlite`/`postgresql` `insert().on_conflict_do_nothing/do_update` — R3) e `gravar_rejeicoes(engine, fonte, rejeicoes, carga_em)` em `log_qualidade` (vocabulário R7)
- [ ] T008 [P] Criar `pipeline/load/cadastro.py` — carga do cadastro `veiculo` de `PIPELINE_CADASTRO_VEICULOS` (upsert por `placa`, pulado por hash, `fonte_origem` com hash, `km_atual` nunca rebaixado — R4)
- [ ] T009 Criar esqueleto de `pipeline/run_etl.py` — `executar_ciclo()` na ordem cadastro → abastecimento → multas → manutenção → licenciamento, resumo por fonte (`situacao`/`extraidos`/`consolidados`/`rejeitados` — contrato § Retorno), `__main__` com exit code (FR-008; depende de T003/T006/T007/T008)
- [ ] T010 Testes unitários dos normalizadores em `tests/test_pipeline.py` — placa nos 2 formatos + inválidas, 3 formatos de data + serial + `31/02/2026` inválida, decimais com vírgula, todas as grafias de tipo/categoria de `data/seeds/INCONSISTENCIAS.md` (depende de T005)

**Checkpoint**: fundação pronta — user stories podem começar (em paralelo, se houver gente).

---

## Phase 3: User Story 1 - Extração bruta com rastreabilidade (Priority: P1) 🎯 MVP

**Goal**: cada extrator deposita dado **bruto intacto** no `stg_*` com `carga_em` +
`fonte_origem@hash`; é por aqui que o CSV da demo entra (demo-crítico).

**Independent Test**: depositar/expor dados nas 4 fontes, rodar 1 ciclo e verificar staging
populado com bruto intacto (hífen, minúscula, vírgula preservados) + carimbo + origem
(quickstart Cenário 1).

### Implementation for User Story 1

- [ ] T011 [P] [US1] Criar `pipeline/extract/abastecimento.py` — varre `PIPELINE_INBOX` (`*.csv`), pula arquivo de hash já visto, grava colunas verbatim em `stg_abastecimento` (contrato 001 `formatos_arquivo.md`; R1)
- [ ] T012 [P] [US1] Criar `pipeline/extract/multas.py` — `GET {MULTAS_API_URL}/multas` (httpx, timeout 5s — R9), payload bruto **incluindo `cnh`/`gravidade`/`codigo_infracao`** em `stg_multas` (staging é trilha bruta), hash do corpo da resposta
- [ ] T013 [P] [US1] Criar `pipeline/extract/manutencao.py` — lê as 3 abas do `PIPELINE_XLSX_MANUTENCAO` por nome de coluna (colunas fora de ordem OK), aba inesperada → `logging.warning` sem quebrar (edge case), nome da aba em `stg_manutencao.aba_origem`
- [ ] T014 [P] [US1] Criar `pipeline/extract/licenciamento.py` — `SELECT * FROM licenciamento` no `PIPELINE_SQLITE_LICENCIAMENTO` (conexão somente-leitura), duplicatas preservadas em `stg_licenciamento` (dedup é do transform — US1 cenário 4)
- [ ] T015 [US1] Ligar o estágio Extract em `pipeline/run_etl.py` — um lote por fonte com `carga_em` único, `situacao=sem_novidade` quando hash já visto (depende de T011–T014)
- [ ] T016 [US1] Teste de aceitação US1 em `tests/test_pipeline.py` — após 1 ciclo: 4 stagings com bruto intacto + `carga_em` + `fonte_origem` no formato `id@sha256:...`; 2º ciclo sem mudança nas fontes → zero linhas novas de staging (R1)

**Checkpoint**: staging auditável funcionando — US1 testável de forma independente.

---

## Phase 4: User Story 2 - Qualidade: normalizar o que dá, rejeitar com motivo (Priority: P1)

**Goal**: dados heterogêneos convergem para o canônico; inválido vai a `log_qualidade` com
motivo — a evidência direta para a banca (risco nº 1 do briefing).

**Independent Test**: alimentar staging com os dados propositalmente inconsistentes da spec
001, transformar+carregar e verificar consolidado limpo + `log_qualidade` com motivos
(quickstart Cenários 2 e 3).

### Implementation for User Story 2

- [ ] T017 [US2] Criar motor de regras em `pipeline/transform/qualidade.py` — processa só o lote corrente (R2), aplica precedência de motivos placa → data → numéricos → vocabulários → cadastro → dedup (data-model § precedência), dedup intra-lote pela chave natural de cada tabela (R3), retorna `(validos, rejeicoes)`
- [ ] T018 [US2] Mapeamentos por fonte em `pipeline/transform/qualidade.py` — staging→colunas consolidadas das 4 fontes (data-model § por fonte): descarte estrutural de `cnh`/`gravidade`/`codigo_infracao` (FR-011), checagem `veiculo_desconhecido` contra o cadastro (R4), dedup de licenciamento por `(placa, vencimento mais recente)` com preterida → `duplicado` (depende de T017)
- [ ] T019 [US2] Funções de upsert por tabela em `pipeline/load/upsert.py` — `abastecimento`/`manutencao`/`multa` com `do_nothing` sem alvo (cobre `ux_multa_upsert` — ADR-004/R3), `licenciamento` com `do_update` por `placa`, `fonte_origem` copiado do staging (SC-003)
- [ ] T020 [US2] Ligar Transform → Load em `pipeline/run_etl.py` — válidos ao upsert, rejeições a `gravar_rejeicoes()`, contadores no resumo do ciclo (depende de T017–T019)
- [ ] T021 [US2] Teste SC-002 em `tests/test_pipeline.py` — ciclo completo sobre os seeds: 100% das inconsistências **inválidas** de `data/seeds/INCONSISTENCIAS.md` em `log_qualidade` com o motivo previsto; as normalizáveis (hífen, minúscula, vírgula, serial) consolidadas sem rejeição; vocabulários do consolidado ⊆ CHECKs do banco
- [ ] T022 [US2] Testes de edge cases em `tests/test_pipeline.py` — linha corrompida no meio do CSV: válidas entram, inválida rejeitada (nunca tudo-ou-nada); placa canônica sem cadastro → `veiculo_desconhecido`; nenhum valor de `cnh` do staging presente em qualquer consolidada (FR-011, quickstart Cenário 3)

**Checkpoint**: US1+US2 = dado sujo entra, consolidado limpo + log de rejeições sai.

---

## Phase 5: User Story 3 - Carga idempotente (Priority: P1)

**Goal**: N execuções → mesmo estado (consolidadas **e** log); arquivo novo na pasta é
incorporado sozinho — é o gesto da demo ao vivo.

**Independent Test**: rodar o pipeline 2× sobre os mesmos dados e comparar contagens e
conteúdo; depositar `gatilho_demo_abastecimento.csv` e ver só ele ser incorporado
(quickstart Cenários 4 e 5).

### Implementation for User Story 3

- [ ] T023 [US3] Atualização de `veiculo.km_atual` em `pipeline/load/upsert.py` — após upsert de abastecimento, por placa afetada: `MAX(km_hodometro)` consolidado quando superar o atual (nunca rebaixa — R10/FR-010; SQL portável SQLite/Postgres, sem `GREATEST`)
- [ ] T024 [US3] Teste SC-001 em `tests/test_pipeline.py` — dupla execução sem mudança nas fontes: contagens e conteúdo idênticos em todas as consolidadas, staging **e** `log_qualidade`; resumo com `sem_novidade` nas 5 fontes (R1/R2/R3); reprocessar manualmente um lote antigo de staging → consolidadas inalteradas (edge case "staging crescendo")
- [ ] T025 [US3] Teste do momento da demo em `tests/test_pipeline.py` — depositar `data/seeds/gatilho_demo_abastecimento.csv` no inbox: só ele é extraído (demais `sem_novidade`), `km_atual` do veículo A ≥ 4501 (contrato 001); mesmo conteúdo re-depositado com outro nome → estado inalterado (edge case hash — R1)

**Checkpoint**: caminho demo-crítico completo (depositar CSV → consolidado atualizado);
motor da spec 004 já pode ser construído sobre isto.

---

## Phase 6: User Story 4 - Resiliência por fonte (Priority: P2)

**Goal**: falha de uma fonte é registrada e as demais seguem — narrativa de robustez.

**Independent Test**: derrubar a fake_api e rodar o ciclo: 3 fontes processam 100%, falha
registrada, exit code 0 (quickstart Cenário 6).

### Implementation for User Story 4

- [ ] T026 [US4] Isolamento por fonte em `pipeline/run_etl.py` — try/except por extrator+transform+load da fonte; exceção → `log_qualidade` (`fonte`, `registro_bruto`=classe+mensagem, `motivo_rejeicao=fonte_indisponivel`, `carga_em`) + `logging.error`, `situacao=indisponivel` no resumo; CLI: exit 0 com fonte fora, ≠0 só em erro estrutural (banco/esquema — R8, contrato § Invocação)
- [ ] T027 [US4] Teste SC-005 em `tests/test_pipeline.py` — com `MULTAS_API_URL` apontando para porta morta: as outras 3 fontes consolidam 100% dos seus dados no mesmo ciclo, existe registro `fonte_indisponivel` para `multas`, exit code 0; ciclo seguinte com API de volta → fonte volta a `ok`/`sem_novidade`

**Checkpoint**: todas as user stories funcionais e testáveis de forma independente.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: documentação exigida por FR-009 e validação de ponta a ponta.

- [ ] T028 [P] Criar `pipeline/README.md` — FR-009 (task 10 da Fase 1 do kanban): tabela de regras de qualidade por fonte (regra → exemplo → destino), vocabulário de motivos (R7), formato de `fonte_origem`, semântica `duplicado` × idempotência (R2/R3), como rodar 1 ciclo
- [ ] T029 [P] Atualizar `README.md` (raiz) — roadmap Fase 1: marcar tasks 4–10 entregues; seção "como rodar": adicionar o ciclo do pipeline (`uv run python -m pipeline.run_etl`) aos comandos existentes
- [ ] T030 Validar `quickstart.md` de ponta a ponta — executar Cenários 1–8 num banco limpo, cronometrar o ciclo (SC-004 < 1 min) e registrar o tempo no PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências.
- **Foundational (Phase 2)**: depende do Setup — **BLOQUEIA todas as user stories** (T009 depende de T003/T006/T007/T008).
- **US1 (Phase 3)**: depende da Phase 2. É o MVP.
- **US2 (Phase 4)**: depende da Phase 2 + T015 (staging populado pelo Extract) para o teste de aceitação.
- **US3 (Phase 5)**: depende de US2 (idempotência só é observável com T→L ligados).
- **US4 (Phase 6)**: depende de T015 (orquestração com as 4 fontes ligadas); independente de US2/US3.
- **Polish (Phase 7)**: T028/T029 após US2; T030 após tudo.

### User Story Dependencies

- **US1 (P1)**: só Foundational — independente das demais.
- **US2 (P1)**: consome o staging de US1 (fluxo E→T é sequencial por natureza); testável de forma independente semeando staging na mão se necessário.
- **US3 (P1)**: refina o Load de US2 (km_atual) e prova a idempotência do conjunto.
- **US4 (P2)**: ortogonal a US2/US3 — pode andar em paralelo com elas após T015.

### Parallel Opportunities

- Phase 1: T003 ∥ T004 (após T001/T002).
- Phase 2: T006 ∥ T007 ∥ T008 (arquivos distintos, após T005 nada — T005 independe; T006–T008 não dependem de T005).
- Phase 3: **T011 ∥ T012 ∥ T013 ∥ T014** — os 4 extratores são arquivos distintos (maior ganho de paralelismo da spec; papéis 🗂️ Dados podem dividir).
- Phase 6 ∥ Phases 4–5: US4 (T026–T027) pode andar em paralelo com US2/US3 por outra pessoa (arquivos: run_etl.py × transform/load — atenção ao merge em run_etl.py com T020).
- Phase 7: T028 ∥ T029.

## Parallel Example: User Story 1

```bash
# Após o checkpoint da Phase 2, lançar os 4 extratores em paralelo:
Task: "T011 extrator de abastecimento em pipeline/extract/abastecimento.py"
Task: "T012 extrator de multas em pipeline/extract/multas.py"
Task: "T013 extrator de manutenção em pipeline/extract/manutencao.py"
Task: "T014 extrator de licenciamento em pipeline/extract/licenciamento.py"
# Depois, sequencial: T015 (integração no run_etl) → T016 (teste de aceitação)
```

---

## Implementation Strategy

### MVP First

1. Phases 1–2 (Setup + Foundational).
2. Phase 3 (US1): staging auditável — **MVP testável** (quickstart Cenário 1).
3. **Demo-crítico mínimo = Phases 3→5 (US1+US2+US3)**: é o caminho "depositar CSV →
   consolidado atualizado" que o motor (spec 004) e o disparo ao vivo exigem — as três são
   P1 e formam o incremento que destrava a spec 004.
4. Phase 6 (US4, P2) e Phase 7 fecham robustez e documentação (FR-009 é exigência do
   briefing — não pular T028).

### Incremental Delivery

Cada checkpoint é um estado demonstrável: staging bruto (US1) → consolidado limpo + log
(US2) → idempotência + gesto da demo (US3) → resiliência (US4) → documentação (Polish).
Commits por task ou grupo lógico, em português com prefixo convencional (CLAUDE.md).

---

## Notes

- Total: **30 tasks** (Setup 4 · Foundational 6 · US1 6 · US2 6 · US3 3 · US4 2 · Polish 3).
- Tasks de teste compartilham `tests/test_pipeline.py` — por isso não levam [P] entre si.
- O esquema do banco NÃO muda nesta spec (zero migration); qualquer necessidade de mudança
  descoberta na implementação volta para a spec 002 (contrato de estabilidade).
- Acesso a banco sempre via `db.config.get_engine()`/`get_session()` (contrato 002).
