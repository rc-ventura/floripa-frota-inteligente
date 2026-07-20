---
description: "Task list — Motor de Alertas Preventivos e Agendamento (spec 004)"
---

# Tasks: Motor de Alertas Preventivos e Agendamento

**Input**: Design documents from `/specs/004-motor-alertas/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/motor_alertas.md](./contracts/motor_alertas.md), [quickstart.md](./quickstart.md)

**Tests**: INCLUÍDOS — a spec exige testes automatizados (FR-008, SC-006) e o kanban os trata como
critério de aceite. Cada gatilho e a idempotência têm task de teste em `tests/test_alertas.py`.

**Organization**: Tarefas agrupadas por user story (prioridade da spec). Ordem de prioridade:
US1 (P1) → US2 (P1) → US5 (P1) → US3 (P2) → US4 (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivo diferente, sem dependência pendente)
- **[Story]**: user story (US1–US5); tarefas de Setup/Foundational/Polish não levam label
- Todo caminho de arquivo é relativo à raiz do repositório

## Path Conventions

Single project Python (plan.md): motor em `alertas/`, agendador em `scheduler.py` na raiz, testes
em `tests/`. Reaproveita `db/` (spec 002) e `pipeline/` (spec 003), já entregues.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependências e esqueleto do pacote do motor.

- [ ] T001 [P] Adicionar a dependência do agendador com `uv add "apscheduler>=3.10,<4"` (atualiza `pyproject.toml` e `uv.lock`; série 3.x estável — research R1)
- [ ] T002 [P] Criar o pacote do motor em `alertas/__init__.py` (arquivo vazio, torna `alertas` importável como `pipeline`)
- [ ] T003 [P] Adicionar `CICLO_INTERVALO_SEGUNDOS` (default `90`) ao `.env.example`, na seção do agendador, com comentário de uso (constitution V, research R9)
- [ ] T004 [P] Criar `alertas/config.py` com `intervalo_ciclo_segundos() -> int` lendo `CICLO_INTERVALO_SEGUNDOS` do ambiente (default 90), espelhando o estilo de `pipeline/config.py`

**Checkpoint**: pacote `alertas` importável, dependência disponível, intervalo parametrizado.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: núcleo compartilhado por TODAS as user stories — regras puras, leitura do estado
consolidado, primitiva de inserção idempotente e o esqueleto de `verificar_alertas()`.

**⚠️ CRITICAL**: nenhuma user story pode começar antes desta fase.

- [ ] T005 [P] Criar `alertas/regras.py` com funções puras (sem banco): `km_confiavel(km_atual, km_no_momento) -> bool` (R5: `km_atual>0` ∧ `km_no_momento` presente ∧ `km_atual ≥ km_no_momento`), `dispara_km(km_desde, limite_km, antecedencia_km) -> bool` e `dispara_tempo(dias_desde, limite_dias, antecedencia_dias) -> bool` (arquitetura §5.1)
- [ ] T006 Criar o esqueleto de `alertas/motor.py::verificar_alertas(hoje: date | None = None) -> dict`: obtém sessão via `db.config.get_session()`, itera `veiculo`, **relê `limiar_config` a cada chamada** (sem cache — FR-002/SC-002) filtrando por `tipo_veiculo`, consulta a última `manutencao` por `(placa, tipo)` com `ORDER BY data DESC LIMIT 1` (índice `ix_manutencao_placa_tipo_data`, R8), e retorna o dicionário-resumo com contadores zerados (`veiculos_avaliados`, `criados_km`, `criados_tempo`, `criados_dados_insuficientes`, `ja_ativos`) — sem disparar gatilho ainda (contrato § Retorno)
- [ ] T007 Implementar a primitiva idempotente `criar_alerta(...)` em `alertas/motor.py`: INSERT em `alerta` dentro de `session.begin_nested()` (SAVEPOINT); em `IntegrityError` do índice `ux_alerta_ativo` faz rollback do savepoint e incrementa `ja_ativos` (no-op); em sucesso incrementa `criados_<tipo_gatilho>`; contagem por inserts efetivos (dialeto-agnóstica, **nunca** `rowcount` — R4, learning lesson) e preenche `gerado_em=datetime.now()`, `situacao='ativo'` (depende de T006)
- [ ] T008 Adicionar entrada CLI a `alertas/motor.py` (`python -m alertas.motor`): imprime o resumo, `sys.exit(0)` em execução normal e `≠0` só em erro estrutural (banco inacessível/esquema ausente), espelhando `pipeline/run_etl.py` (depende de T006)

**Checkpoint**: `verificar_alertas()` percorre a frota, lê limiares sem cache e sabe inserir de
forma idempotente — pronto para plugar os gatilhos.

---

## Phase 3: User Story 1 - Alerta preventivo por quilometragem (Priority: P1) 🎯 MVP

**Goal**: gerar alerta `km` quando `km_atual − km_no_momento ≥ limite_km − antecedencia_km`, ligado
ao `limiar_id` — o gatilho do disparo ao vivo da demo.

**Independent Test**: popular um veículo com `km_atual` e última manutenção conhecidos + limiar em
`LIMIAR_CONFIG`, rodar `verificar_alertas` e conferir o alerta `km` (e a ausência dele abaixo da janela).

- [ ] T009 [US1] Plugar o gatilho **km** no laço de `alertas/motor.py::verificar_alertas`: para cada par avaliável com km confiável (`regras.km_confiavel`), calcular `km_desde = km_atual − ultima.km_no_momento` e chamar `criar_alerta(placa, tipo_gatilho="km", limiar_id=L.id, detalhe=...)` quando `regras.dispara_km(...)` (depende de T007, T005)
- [ ] T010 [US1] Escrever teste do gatilho km em `tests/test_alertas.py`: fixture com banco SQLite em `tmp_path` + `db.init_db.main()` (padrão de `tests/test_pipeline.py`); veículo/limiar/`km_atual` lidos dos seeds (`data/seeds/veiculos.json`, sem valores mágicos), `hoje` injetado; assert alerta `km` criado com `limiar_id` correto (cenário 1) e nenhum alerta quando abaixo da janela (cenário 2)
- [ ] T011 [US1] Adicionar teste de edição de limiar ao vivo (SC-004) em `tests/test_alertas.py`: `UPDATE limiar_config` entre duas chamadas de `verificar_alertas` → a 2ª usa o novo valor imediatamente (prova de que não há cache de processo)

**Checkpoint**: MVP — o motor dispara o alerta por km de forma parametrizada e reage à edição de limiar.

---

## Phase 4: User Story 2 - Alerta preventivo por tempo (Priority: P1)

**Goal**: gerar alerta `tempo` quando `hoje − data_última ≥ limite_dias − antecedencia_dias`,
ligado ao `limiar_id`.

**Independent Test**: popular a última manutenção de um tipo com data conhecida + limiar de dias e
rodar a verificação; o veículo B da demo (166 dias) dispara sozinho.

- [ ] T012 [US2] Plugar o gatilho **tempo** no laço de `alertas/motor.py::verificar_alertas`: `dias_desde = (hoje − ultima.data).days` e `criar_alerta(placa, tipo_gatilho="tempo", limiar_id=L.id, detalhe=...)` quando `regras.dispara_tempo(...)` (depende de T007, T005; edita a mesma função de T009 — sequencial)
- [ ] T013 [US2] Escrever teste do gatilho tempo em `tests/test_alertas.py`: usar o veículo B da demo (`demo_gatilho_tipo == "tempo"`, `TND8453`) dos seeds com `hoje` injetado tal que a antecedência de dias esteja cruzada → alerta `tempo`; e um caso dentro do prazo → nenhum alerta

**Checkpoint**: os dois gatilhos obrigatórios do briefing funcionam e são testados.

---

## Phase 5: User Story 5 - Ciclo agendado de ponta a ponta (Priority: P1)

**Goal**: ETL + motor rodando sozinhos em ciclo único, ordenado e configurável, sem ação manual.

**Independent Test**: configurar intervalo curto, depositar o CSV de gatilho da spec 001 e
cronometrar até o alerta existir no banco.

- [ ] T014 [US5] Criar `scheduler.py` na raiz: define `executar_ciclo_e_verificar()` que chama `pipeline.run_etl.executar_ciclo()` e, na sequência, `alertas.motor.verificar_alertas()` (ordem da arquitetura §8); agenda-a num `BlockingScheduler` do APScheduler com `IntervalTrigger(seconds=alertas.config.intervalo_ciclo_segundos())`, `max_instances=1`, `coalesce=True`; `logging` do resumo e shutdown limpo em SIGINT/SIGTERM (depende de T006, T004, T001; ciclo da spec 003 via contrato `executar_ciclo()`)
- [ ] T015 [US5] Escrever teste de ciclo ordenado em `tests/test_alertas.py`: chamar `scheduler.executar_ciclo_e_verificar()` diretamente (sem subir o `BlockingScheduler`); depois de depositar `data/seeds/gatilho_demo_abastecimento.csv` no inbox, um ciclo ingere o km novo **e** dispara o alerta km sem passo manual (US5.1); e uma fonte indisponível no ETL não impede a verificação de rodar sobre o estado consolidado (US5.3, resiliência herdada de SC-005 da spec 003)

**Checkpoint**: depositar um CSV resulta em alerta no banco em ≤1 ciclo, tudo automático; intervalo troca por env var (SC-005).

---

## Phase 6: User Story 3 - Idempotência e histórico permanente (Priority: P2)

**Goal**: nunca duplicar alertas ativos a cada ciclo; histórico permanente (resolvido nunca some;
recorrência cria nova linha). O mecanismo já existe (T007); esta fase prova e blinda a propriedade.

**Independent Test**: rodar a verificação várias vezes sobre o mesmo estado e contar alertas;
resolver um alerta e conferir que permanece; reativar a condição e conferir recorrência.

- [ ] T016 [US3] Escrever teste de idempotência (SC-002) + isolamento de camada (FR-007) em `tests/test_alertas.py`: rodar `verificar_alertas` **10 vezes** sobre o mesmo estado → contagem de alertas `ativo` estável (igual à 1ª rodada); da 2ª rodada em diante o resumo traz `criados_* == 0` e `ja_ativos > 0`; e asseverar que a verificação **não escreve** em `stg_*` nem `log_qualidade` (contagens inalteradas) — o motor só toca `alerta` (leitura de staging/arquivo é vedada por construção, FR-007)
- [ ] T017 [US3] Escrever teste de histórico/recorrência em `tests/test_alertas.py`: após criar um alerta, `UPDATE alerta SET situacao='resolvido'` e re-rodar → a linha resolvida **permanece** (nenhum DELETE) e uma **nova** linha `ativo` é criada se a condição persistir (US3.2/US3.3; confirma o índice parcial só ver ativos e o motor ser create-only — R7)

**Checkpoint**: painel não vira spam; histórico de notificações preservado (briefing 4.3).

---

## Phase 7: User Story 4 - Dados insuficientes viram alerta, não silêncio (Priority: P2)

**Goal**: veículo impossível de avaliar gera **um** alerta `dados_insuficientes` (por veículo), com
`limiar_id` NULL e `detalhe` explicando o que falta — nunca é pulado.

**Independent Test**: incluir veículo sem manutenção de um tipo aplicável (ou com km não confiável) e
rodar a verificação.

- [ ] T018 [US4] Plugar a coleta de impedimentos + emissão de `dados_insuficientes` em `alertas/motor.py::verificar_alertas`: por veículo, acumular causas (sem limiar para o `tipo_veiculo`; par avaliável sem última manutenção; km não confiável por `regras.km_confiavel`) e, havendo ≥1, `criar_alerta(placa, tipo_gatilho="dados_insuficientes", limiar_id=None, detalhe="; ".join(causas))` — um por veículo (R6; edita a mesma função de T009/T012 — sequencial)
- [ ] T019 [US4] Escrever teste de `dados_insuficientes` (SC-003) em `tests/test_alertas.py`: veículo com tipo avaliável mas sem manutenção → exatamente **um** alerta `dados_insuficientes` com `limiar_id IS NULL` e `detalhe` não-vazio; caso de km não confiável (`km_atual < km_no_momento`) → mesmo tratamento; assert de que nenhum veículo elegível fica sem linha em `alerta` (zero pulados em silêncio)

**Checkpoint**: comportamento diante de dado inconsistente é explícito e testado (briefing 5).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: documentação, validação de release e suíte verde.

- [ ] T020 [P] Criar `alertas/README.md` documentando as regras de disparo, os pontos de entrada (`verificar_alertas`, `python -m alertas.motor`, `scheduler.py`) e as env vars — análogo a `pipeline/README.md`
- [ ] T021 [P] Atualizar o `README.md` da raiz com a seção "rodar o motor e o agendador" (comandos `python -m alertas.motor` e `python scheduler.py`, e `CICLO_INTERVALO_SEGUNDOS`)
- [ ] T022 Validar o [quickstart.md](./quickstart.md) de ponta a ponta nos **dois dialetos**: SQLite (dev) e PostgreSQL 16 (container descartável) — Cenários 1–3 e 6, confirmando idempotência real no dialeto da demo (learning lesson "dois bancos-alvo")
- [ ] T023 [P] Rodar a suíte completa `uv run pytest -q` e garantir verde (regressão das specs 002/003 + novos testes do motor)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências — pode começar já.
- **Foundational (Phase 2)**: depende do Setup — **BLOQUEIA** todas as user stories.
- **User Stories (Phase 3–7)**: dependem da Foundational. Em prioridade: US1 → US2 → US5 → US3 → US4.
- **Polish (Phase 8)**: depende das user stories desejadas concluídas.

### User Story Dependencies

- **US1 (P1)**: só depende da Foundational. É o MVP.
- **US2 (P1)**: só depende da Foundational; independente de US1 na lógica (gatilho distinto), mas
  edita a mesma função `verificar_alertas` → serializa após T009.
- **US5 (P1)**: depende da Foundational (`verificar_alertas`) + Setup (APScheduler, config). Costura
  com `executar_ciclo()` da spec 003. Testável de forma independente via `executar_ciclo_e_verificar()`.
- **US3 (P2)**: depende da Foundational (a primitiva idempotente T007). São tarefas de teste — a
  propriedade já é garantida por construção; US3 a prova.
- **US4 (P2)**: depende da Foundational; edita a mesma função `verificar_alertas` → serializa após
  T009/T012.

### Within Each User Story

- Modelos/entidades: nenhum novo (esquema é da spec 002).
- Regras puras (Foundational) antes das ligações no laço; ligação no laço antes do teste da story.
- Testes podem ser escritos antes da ligação (falham) e passar depois — workflow test-first.

### Parallel Opportunities

- **Setup**: T001–T004 são todos `[P]` (arquivos distintos: `pyproject.toml`/`uv.lock`,
  `alertas/__init__.py`, `.env.example`, `alertas/config.py`).
- **Foundational**: T005 (`regras.py`) é `[P]` com o Setup e independe de T006–T008.
- **Ligações no laço** (T009, T012, T018) editam a MESMA função em `alertas/motor.py` → **não**
  são paralelas entre si (sem `[P]`); a lógica de cada gatilho é independente, mas o arquivo colide.
- **Testes** vivem todos em `tests/test_alertas.py` → sequenciais entre si (mesmo arquivo).
- **Polish**: T020, T021, T023 são `[P]` (arquivos distintos); T022 é manual/ambiente.

---

## Parallel Example: Setup + início da Foundational

```bash
# Podem ser tocados em paralelo (arquivos distintos):
Task T001: uv add "apscheduler>=3.10,<4"          # pyproject.toml + uv.lock
Task T002: criar alertas/__init__.py
Task T003: acrescentar CICLO_INTERVALO_SEGUNDOS ao .env.example
Task T004: criar alertas/config.py
Task T005: criar alertas/regras.py (funções puras)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 (Setup) + Phase 2 (Foundational).
2. Phase 3 (US1 — gatilho km).
3. **PARE e VALIDE**: rodar `python -m alertas.motor` sobre os seeds; conferir o alerta km e a
   reação à edição de limiar. Este é o coração da métrica binária da demo.

### Incremental Delivery (ordem demo-crítica primeiro)

1. Setup + Foundational → base pronta.
2. US1 (km) → MVP, testável isolado.
3. US2 (tempo) → veículo B dispara sozinho no 1º ciclo.
4. US5 (ciclo agendado) → depositar CSV vira alerta sem ação manual (fecha a demo ao vivo).
5. US3 (idempotência/histórico) → sem spam, histórico preservado.
6. US4 (dados insuficientes) → nenhum veículo pulado em silêncio.
7. Polish → docs + validação nos dois bancos + suíte verde.

### Parallel Team Strategy

- Um dev toca Setup + Foundational.
- Depois da Foundational, como as ligações de gatilho colidem no mesmo arquivo, dividir por
  **camada** em vez de por story: um dev nas ligações do laço (US1→US2→US4, sequencial), outro no
  `scheduler.py` (US5) e nos testes de idempotência/histórico (US3), que são arquivos distintos.

---

## Notes

- `[P]` = arquivos distintos, sem dependência pendente.
- Label `[Story]` liga a tarefa à user story (rastreabilidade).
- Nenhuma tabela/migration nova — o esquema `alerta`/`limiar_config` é da spec 002 (entregue).
- O motor conversa **só** pelo banco; nunca lê staging nem arquivo-fonte (constitution VI, FR-007).
- Proibido DELETE/UPDATE de `alerta` no motor: create-only; resolução é ação manual (R7).
- Commit por tarefa ou grupo lógico, em português no imperativo com prefixo convencional.
- Validar nos dois dialetos antes do commit final (learning lesson "dois bancos-alvo").
