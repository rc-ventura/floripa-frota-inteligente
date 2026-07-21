# Feature Specification: Motor de Alertas Preventivos e Agendamento

**Feature Branch**: `feature/004-motor-alertas`

**Created**: 2026-07-13 · **Refinada**: 2026-07-20 (com os contratos das specs 002 e 003 já entregues)

**Status**: Draft (pronta para `/speckit-clarify` ou `/speckit-plan`)

**Input**: User description: "Motor de alertas por km e por tempo com antecedência configurável, idempotente, com histórico permanente e alerta de dados insuficientes, rodando em ciclo agendado junto com o ETL, conforme arquitetura seções 5 e 8."

**Papel responsável**: ⚙️ Backend · **Fases do kanban**: Fase 2 (tasks 1–4 e 6) · **Depende de**: 002 (tabelas `LIMIAR_CONFIG` e `ALERTA` — **entregue**), 003 (dados consolidados + ponto de entrada do ciclo `executar_ciclo()` — **entregue**) · 🔴 demo-crítico

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alerta preventivo por quilometragem (Priority: P1)

Como gestor da frota, quero ser alertado quando um veículo se aproxima do limite de km para uma manutenção — antes de estourar o limite, com a antecedência configurada —, para agendar a preventiva em vez de pagar a corretiva.

**Why this priority**: É o gatilho do disparo ao vivo da demo (o CSV depositado atualiza `veiculo.km_atual` via pipeline) — o caminho da métrica binária de sucesso do briefing.

**Independent Test**: Popular um veículo com `km_atual` conhecido e última manutenção conhecida de um tipo, garantir o limiar correspondente em `LIMIAR_CONFIG`, rodar a verificação e conferir o alerta.

**Acceptance Scenarios**:

1. **Given** um veículo cujo `km_atual − km_no_momento` da última manutenção do tipo `≥ limite_km − antecedencia_km`, **When** a verificação roda, **Then** um alerta com gatilho `km` é criado, vinculado ao limiar (`limiar_id`) que o parametrizou.
2. **Given** um veículo ainda abaixo da janela de antecedência, **When** a verificação roda, **Then** nenhum alerta é criado.
3. **Given** um veículo a poucos km da janela e um limiar que é **editado ao vivo em `LIMIAR_CONFIG`** (sem reiniciar o sistema), **When** a verificação seguinte roda, **Then** ela usa o novo valor imediatamente e o alerta reage à mudança — o motor lê a configuração a cada verificação, sem cache de processo (herda SC-002 da spec 002).
4. **Given** os cenários acima, **When** a suíte de testes roda, **Then** existe teste automatizado cobrindo o disparo por km (critério de aceite do kanban).

---

### User Story 2 - Alerta preventivo por tempo (Priority: P1)

Como gestor da frota, quero ser alertado quando faz tempo demais desde a última manutenção de um tipo (com antecedência em dias), para cobrir veículos que rodam pouco mas envelhecem igual.

**Why this priority**: Segundo gatilho obrigatório do briefing (4.3); o veículo B da demo nasce com a antecedência de tempo já cruzada (166 dias; limiar `limite_dias − antecedencia_dias = 165`), então o alerta dele aparece **sozinho no primeiro ciclo do motor**, evidenciando este gatilho sem manipulação ao vivo.

**Independent Test**: Popular a última manutenção de um tipo com data conhecida, garantir o limiar de dias e rodar a verificação.

**Acceptance Scenarios**:

1. **Given** um veículo cujo `hoje − data da última manutenção do tipo ≥ limite_dias − antecedencia_dias`, **When** a verificação roda, **Then** um alerta com gatilho `tempo` é criado, vinculado ao limiar.
2. **Given** um veículo dentro do prazo, **When** a verificação roda, **Then** nenhum alerta de tempo é criado.
3. **Given** os cenários acima, **When** a suíte de testes roda, **Then** existe teste automatizado cobrindo o disparo por tempo.

---

### User Story 3 - Idempotência e histórico permanente (Priority: P2)

Como gestor, não quero ser notificado em duplicidade a cada ciclo (o job roda a cada poucos minutos), e preciso do histórico completo de notificações — alertas atendidos mudam de situação, nunca somem.

**Why this priority**: Sem idempotência o painel vira spam a cada ciclo de 1–2 min; o histórico é o "registro de notificações" exigido pelo briefing (4.3).

**Independent Test**: Rodar a verificação várias vezes seguidas sobre o mesmo estado e contar alertas; resolver um alerta e conferir que permanece consultável; reativar a condição e conferir recorrência.

**Acceptance Scenarios**:

1. **Given** um alerta já `ativo` para uma dada (placa, tipo de gatilho, limiar), **When** a verificação roda de novo, **Then** nenhum alerta duplicado é criado (o motor trata a colisão como no-op, apoiado na unicidade de alerta ativo garantida pelo banco na spec 002).
2. **Given** um alerta atendido, **When** marcado como `resolvido`, **Then** ele permanece no histórico com a situação atualizada — nunca é apagado (proibido DELETE em `ALERTA`).
3. **Given** um alerta `resolvido` e a condição de disparo reocorrendo, **When** a verificação roda, **Then** um novo alerta `ativo` pode ser criado — o resolvido não bloqueia a recorrência.

---

### User Story 4 - Dados insuficientes viram alerta, não silêncio (Priority: P2)

Como gestor, preciso saber quais veículos o sistema não consegue avaliar (sem manutenção registrada ou sem km confiável) — um veículo ignorado silenciosamente é um risco invisível.

**Why this priority**: Comportamento diante de dados inconsistentes é critério de avaliação explícito do briefing (seção 5).

**Independent Test**: Incluir veículo sem histórico de manutenção de um tipo aplicável e rodar a verificação.

**Acceptance Scenarios**:

1. **Given** um veículo com ao menos um tipo aplicável que não pode ser avaliado (sem manutenção registrada daquele tipo), **When** a verificação roda, **Then** **um** alerta `dados_insuficientes` é criado **por veículo** (com `limiar_id` nulo e `detalhe` enumerando todas as causas), em vez de o veículo ser pulado — como `limiar_id` é nulo, existe no máximo um `dados_insuficientes` ativo por placa, e o `detalhe` agrega os impedimentos de todos os tipos.
2. **Given** um veículo com km não confiável (ausente, ou leitura inconsistente com o histórico do hodômetro — ADR-002), **When** a verificação roda, **Then** o mesmo tratamento se aplica, com o `detalhe` explicando a causa.
3. **Given** um veículo com um tipo avaliável e vencido (gera `km`/`tempo`) e outro tipo sem histórico, **When** a verificação roda, **Then** coexistem o alerta do gatilho e **um** `dados_insuficientes` (gatilhos distintos, ambos ativos) — o `dados_insuficientes` não suprime os demais.

---

### User Story 5 - Ciclo agendado de ponta a ponta (Priority: P1)

Como apresentador da demo, preciso que ETL e motor rodem sozinhos em ciclo configurável (1–2 min na demo, sem tocar em código), para que depositar um CSV na pasta resulte em alerta no painel sem nenhuma ação manual.

**Why this priority**: É a automação que costura a demo ao vivo (task 6 da Fase 2, demo-crítica); sem ela cada passo seria manual.

**Independent Test**: Configurar intervalo curto, depositar o CSV de gatilho da spec 001 e cronometrar até o alerta existir no banco.

**Acceptance Scenarios**:

1. **Given** o sistema no ar com intervalo configurado por variável de ambiente, **When** um CSV novo entra na pasta monitorada, **Then** no ciclo seguinte o pipeline ingere o dado (`executar_ciclo()` da spec 003) **e** a verificação de alertas roda na sequência, sem intervenção manual.
2. **Given** o intervalo alterado na configuração, **When** o sistema reinicia, **Then** o novo intervalo vale sem alteração de código.
3. **Given** uma fonte do ETL indisponível num ciclo, **When** o ciclo roda, **Then** o motor ainda executa a verificação sobre o estado consolidado disponível (a resiliência do ETL — SC-005 da spec 003 — não bloqueia o motor).

### Edge Cases

- Par (tipo_veiculo, tipo_manutencao) **sem linha** em `LIMIAR_CONFIG`: é "não-avaliável" para aquele par (o contrato da spec 002 proíbe default silencioso) — o motor o ignora para aquele tipo, sem erro que derrube o ciclo; se o veículo não tiver nenhum tipo avaliável, recai em `dados_insuficientes`.
- `km_atual` menor que `km_no_momento` da última manutenção (odômetro inconsistente): km não confiável → `dados_insuficientes`. A série `km_hodometro` do `ABASTECIMENTO` consolidado (ADR-002) pode servir de evidência adicional (leituras decrescentes).
- Limiar alterado com alerta `ativo` existente: o alerta ativo não é apagado nem alterado retroativamente pelo motor; a próxima verificação usa o novo limiar e pode gerar recorrência (nova linha `ativo`) se a condição voltar a valer. O motor é *create-only* — **nunca resolve automaticamente**; resolver um alerta é ação manual (painel/script), conforme Assumptions.
- Duas condições verdadeiras ao mesmo tempo (km **e** tempo) para o mesmo veículo/tipo: dois alertas distintos, um por gatilho.
- Ciclo do motor coincidindo com o ETL: a verificação roda **após** a carga do ciclo (sequência da arquitetura §8), lendo estado consolidado consistente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Para cada veículo × tipo de manutenção **avaliável**, o motor MUST avaliar as duas condições (arquitetura §5.1): disparo por km e disparo por tempo, ambas descontando a antecedência configurada.
- **FR-002**: Limites e antecedências MUST vir exclusivamente de `LIMIAR_CONFIG` (por tipo de veículo × tipo de manutenção), lidos **a cada verificação** (sem cache de processo, para que edição ao vivo tenha efeito imediato — SC-002 da spec 002); nunca de constantes no código.
- **FR-003**: O motor MUST ser idempotente: não cria alerta novo se já existe alerta `ativo` para a mesma (placa, tipo de gatilho, limiar). A unicidade de alerta ativo é garantida pelo banco (spec 002); o motor trata a colisão como no-op.
- **FR-004**: Alertas MUST ser permanentes: transição apenas de situação (`ativo` → `resolvido`), nunca exclusão; recorrência após resolução cria **nova** linha `ativo`. A transição para `resolvido` é ação **externa** (painel/script) — o motor apenas cria (*create-only*). A tabela `ALERTA` é o histórico de notificações do briefing (4.3).
- **FR-005**: Veículo impossível de avaliar MUST gerar alerta `dados_insuficientes`, com `limiar_id` nulo e `detalhe` indicando o que falta (sem manutenção registrada, km não confiável, etc.) — nunca ser pulado em silêncio.
- **FR-006**: ETL e motor MUST rodar em ciclo agendado único e ordenado (extração → transformação → carga → verificação de alertas), com o intervalo parametrizado por variável de ambiente; o motor aciona o ciclo do ETL pelo ponto de entrada da spec 003 (`executar_ciclo()`).
- **FR-007**: O motor MUST comunicar-se exclusivamente pelo banco consolidado — nunca lê staging nem arquivos-fonte (princípio central da arquitetura §1).
- **FR-008**: Os gatilhos por km e por tempo, a idempotência e o caso `dados_insuficientes` MUST ter testes automatizados (critério de aceite do kanban).

### Key Entities

- **Alerta** (`ALERTA`, spec 002): placa, `limiar_id` (nulo em `dados_insuficientes`), `tipo_gatilho` (`km` | `tempo` | `dados_insuficientes`), `gerado_em`, `situacao` (`ativo` | `resolvido`), `detalhe`.
- **Limiar** (`LIMIAR_CONFIG`, spec 002): fonte exclusiva de parametrização (limite_km, limite_dias, antecedencia_km, antecedencia_dias) por (tipo_veiculo, tipo_manutencao).
- **Estado consolidado** (spec 003): `veiculo.km_atual`, última `MANUTENCAO` por (placa, tipo), série `ABASTECIMENTO.km_hodometro` — insumos de leitura do motor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No cenário determinístico da demo, depositar o arquivo de gatilho resulta em alerta gerado em no máximo **1 ciclo completo** após a ingestão — antes do vencimento real, satisfazendo a métrica binária do briefing.
- **SC-002**: Rodar a verificação **10 vezes seguidas** sobre o mesmo estado produz **zero** alertas duplicados.
- **SC-003**: **100%** dos veículos não-avaliáveis aparecem como `dados_insuficientes`; **zero** veículos silenciosamente ignorados.
- **SC-004**: Editar um limiar em `LIMIAR_CONFIG` altera o resultado da **próxima** verificação sem reiniciar nem alterar código (efeito observável em ≤ 1 ciclo).
- **SC-005**: Alterar o intervalo do ciclo requer **zero** mudanças de código (somente configuração).
- **SC-006**: Os testes automatizados dos dois gatilhos, da idempotência e de `dados_insuficientes` passam na suíte do repositório.

## Assumptions

- O agendador embutido no próprio processo (decisão D4 da arquitetura) é suficiente para a PoC; orquestrador dedicado fica documentado como evolução.
- "Resolver" um alerta na PoC é ação simples (atualização de situação via painel ou script); o fluxo de atendimento completo está fora de escopo.
- O motor lê exclusivamente o banco consolidado — nunca staging nem arquivos-fonte (arquitetura §1; contrato da spec 002).
- As tabelas `LIMIAR_CONFIG` e `ALERTA` e a unicidade de alerta ativo já existem (spec 002, entregue); o pipeline e o ponto de entrada `executar_ciclo()` já existem (spec 003, entregue).
- "Aplicável" por tipo de manutenção = existência de linha em `LIMIAR_CONFIG` para o par (tipo_veiculo, tipo_manutencao); pares sem linha não são avaliados para aquele tipo.

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v2.md` (seções 5, 7-D4 e 8)
- Contrato do esquema (spec 002): `specs/002-modelo-dados-banco/contracts/esquema_tabelas.md` (§ Spec 004 — Motor)
- Contrato do ciclo (spec 003): `specs/003-pipeline-etl/contracts/ciclo_pipeline.md` (ponto de entrada `executar_ciclo()`)
- ADRs: `docs/decisoes/ADR-002` (série de km/hodômetro), `docs/decisoes/ADR-004` (unicidade de alerta ativo com `coalesce(limiar_id,-1)`)
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 2 t1–t4 e t6)
