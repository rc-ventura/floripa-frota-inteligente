# Tasks: Modelo de Dados e Banco Consolidado

**Input**: Design documents de `/specs/002-modelo-dados-banco/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R9), data-model.md (12 tabelas), contracts/esquema_tabelas.md, quickstart.md (Cenários 1–7)

**Tests**: INCLUÍDOS — exigência do projeto (kanban: "testes são critério de aceite"; constitution; quickstart Cenário 7). Escrever cada teste ANTES da implementação da story e vê-lo falhar.

**Organization**: Tarefas agrupadas por user story (US1 esquema · US2 limiares · US3 rastreabilidade/LGPD).

**Nota de paralelismo**: os modelos vivem em um único `db/models.py` e os testes em um único `tests/test_db.py` (plan §Structure) — tarefas no mesmo arquivo NÃO levam `[P]`. O paralelismo real está entre modelos × migration × init × seed × docs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US3)
- Caminhos exatos de arquivo em cada descrição

## Path Conventions

Biblioteca única em `db/` (arquitetura v2 §9): `db/config.py`, `db/models.py`, `db/seed_limiares.py`, `db/init_db.py`, `db/migrations/` (Alembic). Testes em `tests/test_db.py`. Deps no `pyproject.toml` da raiz.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependências instaladas e esqueleto do módulo `db/`

- [X] T001 Adicionar ao `pyproject.toml` as dependências `sqlalchemy>=2.0`, `alembic>=1.13`, `psycopg[binary]>=3.1` (research R9) e rodar `uv sync`
- [X] T002 [P] Criar `db/__init__.py` (vazio), `.env.example` na raiz com `DATABASE_URL` comentada (default documentado: `sqlite:///db/frota.db` — arquitetura §9) e regra no `.gitignore` para `db/frota.db` (banco local nunca versionado); no mesmo commit, atualizar o comentário do `.gitignore` que atribuía o `.env.example` à spec 007 (o arquivo nasce aqui; a 007 apenas o estende com o intervalo do ciclo — achado I2)
- [X] T003 [P] Criar `tests/test_db.py` com fixtures base: fixture que cria banco SQLite em `tmp_path` (via `DATABASE_URL` monkeypatched) e executa a inicialização programática (`db.init_db.main()`); fixture de sessão SQLAlchemy para asserções

**Checkpoint**: `uv sync` verde; `pytest` coleta sem erro

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: acesso a banco, base declarativa e scaffolding do Alembic — pré-requisitos de todas as stories

**⚠️ CRITICAL**: nenhuma story pode começar antes desta fase terminar

- [X] T004 Implementar `db/config.py`: `get_engine()`/`get_session()` resolvendo `DATABASE_URL` da env var com default `sqlite:///db/frota.db`, ponto único de conexão para todas as camadas (research R1; contrato §inicialização)
- [X] T005 Implementar em `db/models.py` a base declarativa SQLAlchemy 2.x: `Base(DeclarativeBase)` com `naming_convention` para constraints (nomes estáveis p/ Alembic) e a constante exportada `REGEX_PLACA_CANONICA = r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"` (ADR-001, research R3)
- [X] T006 Criar scaffolding do Alembic em `db/migrations/`: `alembic.ini` (em `db/`), `env.py` importando `db.models.Base.metadata` e `db.config` (URL única), com `render_as_batch=True` para SQLite (research R2)

**Checkpoint**: `alembic -c db/alembic.ini current` roda sem erro em banco vazio

---

## Phase 3: User Story 1 — Esquema completo criado do zero (Priority: P1) 🎯 MVP

**Goal**: um comando (`python -m db.init_db`) cria as 12 tabelas do ERD v2 (+ constraints, índices e o índice único parcial de alerta ativo) em SQLite e PostgreSQL, de forma idempotente.

**Independent Test**: em ambiente limpo, rodar a inicialização e verificar as 12 tabelas com campos/relacionamentos do data-model (quickstart Cenários 1–2).

### Tests for User Story 1 (escrever primeiro — devem falhar)

- [X] T007 [US1] Escrever `test_criacao_do_zero` em `tests/test_db.py`: após 1 execução existem as 12 tabelas (`veiculo`, `abastecimento`, `manutencao`, `multa`, `licenciamento`, `limiar_config`, `alerta`, 4×`stg_*`, `log_qualidade`) + `alembic_version`; colunas-chave presentes (`km_hodometro`, `categoria`, `fonte_origem`, `detalhe`) (FR-001..FR-003)
- [X] T008 [US1] Escrever `test_placa_e_relacionamentos` em `tests/test_db.py`: inserir veículo com placa antiga (`ABC1234`) e Mercosul (`ABC1D23`) → OK; placa fora do canônico (`AB1234`, `abc1234`) → `ValueError` do `@validates`; evento com placa inexistente → falha de FK; CHECKs de vocabulário rejeitam `tipo`/`categoria`/`situacao` inválidos (US1 cenário 2)
- [X] T009 [US1] Escrever `test_alerta_ativo_unico` em `tests/test_db.py`: 2º alerta ativo idêntico (placa, gatilho, limiar) → `IntegrityError` (índice `ux_alerta_ativo`); resolver o 1º e inserir novo ativo → OK (recorrência não bloqueada); `dados_insuficientes` com `limiar_id` NULL respeita a mesma regra via `coalesce` (research R6, FR-005)

### Implementation for User Story 1

- [X] T010 [US1] Implementar em `db/models.py` as consolidadas de domínio: `Veiculo` (placa PK + CHECK length + `@validates` com `REGEX_PLACA_CANONICA`, `km_atual`, `fonte_origem` — research R8), `Abastecimento` (`km_hodometro` nullable + UNIQUE `(placa, data, km_hodometro)` — ADR-002), `Manutencao` (`tipo` + `categoria` com CHECKs + UNIQUE `(placa, data, tipo)` — ADR-003), `Multa` (sem cnh/gravidade — minimização estrutural; UNIQUE pragmática), `Licenciamento` (placa PK/FK 1:1) — conforme data-model §1
- [X] T011 [US1] Implementar em `db/models.py` `LimiarConfig` (UNIQUE `(tipo_veiculo, tipo_manutencao)`) e `Alerta` (`limiar_id` FK nullable, `tipo_gatilho` CHECK, `situacao` default `ativo`, `detalhe`, índice único parcial `ux_alerta_ativo` sobre `(placa, tipo_gatilho, coalesce(limiar_id,-1))` WHERE `situacao='ativo'` — research R6)
- [X] T012 [US1] Implementar em `db/models.py` as 4 staging (`StgAbastecimento`, `StgMultas` com `cnh` bruta, `StgManutencao` com `aba_origem`, `StgLicenciamento`) — tudo TEXT nullable + `carga_em`/`fonte_origem` NOT NULL — e `LogQualidade` (data-model §2–3, research R5)
- [X] T013 [US1] Declarar em `db/models.py` os 5 índices de consulta do data-model §4 (`ix_abastecimento_placa_data`, `ix_manutencao_placa_tipo_data`, `ix_multa_placa_data`, `ix_alerta_situacao`, `ix_licenciamento_vencimento`)
- [X] T014 [US1] Gerar a migration inicial `db/migrations/versions/0001_esquema_inicial.py` (autogenerate a partir dos modelos + revisão manual: índice parcial com `postgresql_where`/`sqlite_where` e expressão `coalesce` precisam de ajuste manual — research R2/R6)
- [X] T015 [US1] Implementar `db/init_db.py` (executável via `python -m db.init_db`): roda `alembic upgrade head` programaticamente com a URL de `db/config.py` e chama o seed (no-op até a US2); imprime resumo (tabelas criadas, ambiente) (FR-007, contrato §inicialização)

**Checkpoint**: T007–T009 verdes; `python -m db.init_db` 2× seguidas sem erro (SC-004)

---

## Phase 4: User Story 2 — Limiares como dados, não código (Priority: P1)

**Goal**: `limiar_config` semeada do JSON da spec 001 (fonte única) e editável em runtime sem restart — o momento planejado da demo.

**Independent Test**: alterar um valor em `limiar_config` com o sistema no ar e verificar que a próxima leitura usa o novo valor; re-init não desfaz a edição (quickstart Cenários 3–4).

### Tests for User Story 2 (escrever primeiro — devem falhar)

- [X] T016 [US2] Escrever `test_seed_limiares` em `tests/test_db.py`: após init, `limiar_config` tem exatamente as 9 linhas de `data/seeds/limiares_semente.json` (comparação campo a campo); re-init não duplica nem altera (FR-004, quickstart C3); consulta por par inexistente (ex.: `ambulancia`/`pneus`) retorna vazio — ausência detectável, sem default silencioso (edge case da spec; achado U2)
- [X] T017 [US2] Escrever `test_limiar_runtime` em `tests/test_db.py`: UPDATE de `limite_km` via sessão → nova leitura em outra sessão vê o valor sem reinicialização; re-executar o seed NÃO sobrescreve a edição; com `--sobrescrever`, o valor do JSON volta a valer (SC-002, research R4). Nota: este teste é o *proxy* do SC-002 — a verificação plena ("próxima verificação do motor") é assumida pela spec 004, que herda do contrato a proibição de cache de processo (achado C1 do speckit-analyze)

### Implementation for User Story 2

- [X] T018 [US2] Implementar `db/seed_limiares.py`: lê `data/seeds/limiares_semente.json` (caminho resolvido da raiz do repo), upsert por `(tipo_veiculo, tipo_manutencao)` — insere ausentes, nunca sobrescreve existentes por padrão (research R4); executável isolado (`python -m db.seed_limiares`) com flag opcional `--sobrescrever` para recalibração deliberada (JSON alterado → banco existente adota os novos valores; achado U1 do speckit-analyze)
- [X] T019 [US2] Integrar o seed ao `db/init_db.py` (ordem: upgrade → seed) e documentar no help do CLI que par (tipo_veiculo, tipo_manutencao) ausente é "não-avaliável" para o motor — sem default silencioso (edge case da spec)

**Checkpoint**: T016–T017 verdes; demo do limiar ao vivo ensaiável via quickstart C4

---

## Phase 5: User Story 3 — Rastreabilidade e LGPD embutidas no modelo (Priority: P2)

**Goal**: provar por introspecção que auditabilidade (fonte_origem/carga_em) e minimização LGPD (zero de-para, zero coluna de identidade real) são propriedades estruturais do esquema.

**Independent Test**: inspecionar o esquema — toda consolidada tem `fonte_origem`; todo staging tem carimbo; nenhuma estrutura liga pseudônimo a identidade (quickstart Cenário 6).

### Tests for User Story 3 (escrever primeiro — devem falhar)

- [X] T020 [US3] Escrever `test_rastreabilidade_lgpd` em `tests/test_db.py` (introspecção via SQLAlchemy `inspect()`): `fonte_origem` em 100% das consolidadas (incluindo `veiculo`); `carga_em`+`fonte_origem` em 100% das `stg_*`; nenhuma coluna `nome`/`cpf`/`matricula`/`cnh` em consolidadas/`alerta`/`limiar_config`; nenhuma tabela com "condutor" no nome (de-para inexistente) (FR-006, SC-003)

### Implementation for User Story 3

- [X] T021 [US3] Revisar/ajustar `db/models.py` (e regenerar a migration se necessário) até T020 passar — em particular `fonte_origem` no `Veiculo` (research R8) e a ausência estrutural de `cnh`/`gravidade` em `Multa`

**Checkpoint**: as 3 stories verdes de forma independente

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: validação nos dois ambientes, critérios de tempo e sincronização de docs

- [X] T022 [P] Validar o quickstart Cenário 5 (PostgreSQL 16 via Docker): `DATABASE_URL=postgresql+psycopg://... python -m db.init_db` 2× — mesmas tabelas/constraints, índice parcial funcional; registrar o resultado na descrição do MR (D2, SC-001)
- [X] T023 Medir SC-001 (`time python -m db.init_db` < 1 min em banco limpo, SQLite e Postgres) e SC-004 (execução dupla sem erro/perda — inserir 1 registro entre as execuções e conferir sobrevivência)
- [X] T024 Validar `specs/002-modelo-dados-banco/quickstart.md` de ponta a ponta (Cenários 1–7) e corrigir divergências de docs/comandos encontradas
- [X] T025 [P] Sincronizar `specs/002-modelo-dados-banco/contracts/esquema_tabelas.md` com qualquer ajuste feito durante a implementação (contrato é consumido pelas specs 003/004/005/006 — regra de estabilidade do próprio contrato)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — BLOQUEIA as stories (config + Base + Alembic)
- **US1 (Phase 3)**: depende da Phase 2 — é o MVP (esquema é o produto da spec)
- **US2 (Phase 4)**: depende de T011 (LimiarConfig) e T015 (init) — na prática, segue a US1
- **US3 (Phase 5)**: depende dos modelos da US1 (T010–T012); teste é introspecção pura
- **Polish (Phase 6)**: depende de todas as stories

### Within Each User Story

- Teste primeiro (deve falhar) → implementação → teste verde
- Modelos → migration → init/seed

### Parallel Opportunities

- Phase 1: T002 ∥ T003 (após T001)
- US1: T014 (migration) e T015 (init_db) ∥ entre si após T010–T013; testes T007–T009 sequenciais entre si (mesmo arquivo), mas ∥ com T010+ se houver 2 pessoas
- US2: T018 (seed_limiares.py) ∥ com T016–T017 (arquivos diferentes)
- Polish: T022 ∥ T025

---

## Parallel Example: User Story 1

```bash
# Dev A — modelos (sequencial, mesmo arquivo db/models.py):
Task: "T010 consolidadas" → "T011 limiar+alerta" → "T012 staging+log" → "T013 índices"

# Dev B — em paralelo (arquivos diferentes):
Task: "T007–T009 testes em tests/test_db.py"
# depois de T013:
Task: "T014 migration 0001"  ∥  Task: "T015 db/init_db.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2 (Foundational)
2. Phase 3 (US1): esquema completo + init idempotente — **MVP que destrava a spec 003**
3. **PARAR e VALIDAR**: quickstart Cenários 1–2
4. US2 na sequência imediata (o seed é parte do "um comando" do FR-007)

### Incremental Delivery

1. Setup + Foundational → Alembic operacional
2. US1 → 12 tabelas + constraints + `python -m db.init_db` → **spec 003 pode começar os extratores contra `stg_*`**
3. US2 → seed + edição em runtime → **momento da demo ensaiável; spec 004 tem `limiar_config` real**
4. US3 → prova estrutural de compliance → evidência para a banca e para a spec 007 (doc LGPD)
5. Polish → Postgres validado + docs sincronizadas

### Caminho demo-crítico (constitution I)

`T001→T006` → US1 (`T010–T015`) → US2 (`T018–T019`) é o caminho mínimo até o "alterar limiar ao vivo" da demo existir; US3 é compliance e não bloqueia o ensaio.

---

## Notes

- Tarefas `[P]` = arquivos diferentes, sem dependência pendente; `db/models.py` e `tests/test_db.py` são arquivos únicos — respeitar a sequência dentro deles
- O seed lê `data/seeds/limiares_semente.json` — NUNCA duplicar os valores em código (research R4; fonte única com a spec 001)
- Commit após cada tarefa ou grupo lógico; mensagens em português no imperativo (`feat:`, `test:`, `chore:`)
- Cada checkpoint é um ponto de validação independente da story — rodar o teste da story antes de seguir
