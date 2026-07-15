# Feature Specification: Motor de Alertas Preventivos e Agendamento

**Feature Branch**: `feature/004-motor-alertas`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Motor de alertas por km e por tempo com antecedência configurável, idempotente, com histórico permanente e alerta de dados insuficientes, rodando em ciclo agendado junto com o ETL, conforme arquitetura v1 seções 5 e 8."

**Papel responsável**: ⚙️ Backend · **Fases do kanban**: Fase 2 (tasks 1–4 e 6) · **Depende de**: 002 (LIMIAR_CONFIG e ALERTA), 003 (dados consolidados) · 🔴 demo-crítico

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alerta preventivo por quilometragem (Priority: P1)

Como gestor da frota, quero ser alertado quando um veículo se aproxima do limite de km para uma manutenção (antes de estourar o limite, com a antecedência configurada), para agendar a manutenção preventiva em vez de pagar a corretiva.

**Why this priority**: É o gatilho usado no disparo ao vivo da demo (o CSV depositado atualiza km) — o caminho da métrica binária de sucesso do briefing.

**Independent Test**: Popular um veículo com km conhecido e última manutenção conhecida, configurar limiar, rodar a verificação e conferir o alerta.

**Acceptance Scenarios**:

1. **Given** veículo com `km_desde_ultima >= limite_km - antecedencia_km`, **When** a verificação roda, **Then** um alerta com gatilho `km` é criado, vinculado ao limiar que o parametrizou.
2. **Given** veículo abaixo da janela de antecedência, **When** a verificação roda, **Then** nenhum alerta é criado.
3. **Given** os cenários acima, **When** a suíte de testes roda, **Then** existe teste unitário cobrindo o disparo por km (critério de aceite do kanban).

---

### User Story 2 - Alerta preventivo por tempo (Priority: P1)

Como gestor da frota, quero ser alertado quando faz tempo demais desde a última manutenção de um tipo (com antecedência em dias), para cobrir veículos que rodam pouco mas envelhecem igual.

**Why this priority**: Segundo gatilho obrigatório do briefing (4.3); um dos dois veículos da demo nasce a ~20 dias do limiar.

**Independent Test**: Popular última manutenção com data conhecida, configurar limite de dias e rodar a verificação.

**Acceptance Scenarios**:

1. **Given** veículo com `dias_desde_ultima >= limite_dias - antecedencia_dias`, **When** a verificação roda, **Then** um alerta com gatilho `tempo` é criado.
2. **Given** os cenários acima, **When** a suíte de testes roda, **Then** existe teste unitário cobrindo o disparo por tempo.

---

### User Story 3 - Idempotência e histórico permanente (Priority: P2)

Como gestor, não quero ser notificado em duplicidade a cada ciclo (o job roda a cada poucos minutos), e preciso do histórico completo de notificações — alertas atendidos mudam de situação, nunca somem.

**Why this priority**: Sem idempotência o painel vira spam a cada ciclo de 1–2 min; o histórico é o "registro de notificações" exigido pelo briefing (4.3).

**Independent Test**: Rodar a verificação várias vezes seguidas sobre o mesmo estado e contar alertas; resolver um alerta e conferir que permanece consultável.

**Acceptance Scenarios**:

1. **Given** um alerta ativo para (placa, tipo de manutenção, gatilho), **When** a verificação roda de novo, **Then** nenhum alerta duplicado é criado.
2. **Given** um alerta atendido, **When** marcado como resolvido, **Then** ele permanece no histórico com a situação atualizada — nunca é apagado.
3. **Given** um alerta resolvido e a condição de disparo persistindo/reocorrendo, **When** a verificação roda, **Then** um novo alerta ativo pode ser criado (o resolvido não bloqueia recorrência).

---

### User Story 4 - Dados insuficientes viram alerta, não silêncio (Priority: P2)

Como gestor, preciso saber quais veículos o sistema não consegue avaliar (sem manutenção registrada ou sem km confiável) — um veículo ignorado silenciosamente é um risco invisível.

**Why this priority**: Comportamento diante de dados inconsistentes é critério de avaliação explícito do briefing (seção 5).

**Independent Test**: Incluir veículo sem histórico de manutenção e rodar a verificação.

**Acceptance Scenarios**:

1. **Given** veículo sem registro de manutenção de um tipo aplicável, **When** a verificação roda, **Then** um alerta especial `dados_insuficientes` é criado em vez de o veículo ser pulado.
2. **Given** veículo com km não confiável (ausente ou inconsistente), **When** a verificação roda, **Then** o mesmo tratamento se aplica.

---

### User Story 5 - Ciclo agendado de ponta a ponta (Priority: P1)

Como apresentador da demo, preciso que ETL e motor rodem sozinhos em ciclo configurável (1–2 min na demo, sem tocar em código), para que depositar um CSV na pasta resulte em alerta no painel sem nenhuma ação manual.

**Why this priority**: É a automação que costura a demo ao vivo (task 6 da Fase 2, demo-crítica); sem ela cada passo seria manual.

**Independent Test**: Configurar intervalo curto, depositar o CSV de gatilho da spec 001 e cronometrar até o alerta existir no banco.

**Acceptance Scenarios**:

1. **Given** o sistema no ar com intervalo configurado por variável de ambiente, **When** um CSV novo entra na pasta monitorada, **Then** no ciclo seguinte o dado é ingerido e a verificação de alertas roda na sequência, sem intervenção manual.
2. **Given** o intervalo alterado na configuração, **When** o sistema é reiniciado, **Then** o novo intervalo vale sem alteração de código.

### Edge Cases

- Par (tipo_veiculo, tipo_manutencao) sem limiar em LIMIAR_CONFIG: definição explícita (tratar como não-aplicável e registrar, ou `dados_insuficientes`) — nunca erro que derrube o ciclo.
- `km_atual` do veículo menor que `km_no_momento` da última manutenção (odômetro inconsistente): km não confiável → `dados_insuficientes`. A série `km_hodometro` do ABASTECIMENTO consolidado (ADR-002) pode ser usada como evidência adicional de inconsistência (leituras decrescentes).
- Limiar alterado com alerta ativo existente: alerta ativo não é retroativamente apagado; a próxima verificação usa o novo limiar.
- Duas condições verdadeiras ao mesmo tempo (km e tempo): dois alertas distintos, um por gatilho.
- Ciclo do motor coincidindo com ETL em andamento: verificação lê estado consistente (roda após o ETL do ciclo, conforme sequência da arquitetura seção 8).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Para cada veículo × tipo de manutenção aplicável, o motor MUST avaliar as duas condições da arquitetura (seção 5.1): disparo por km e disparo por tempo, ambas descontando a antecedência configurada.
- **FR-002**: Os limites e antecedências MUST vir exclusivamente de LIMIAR_CONFIG (por tipo de veículo × tipo de manutenção) — nunca de constantes no código.
- **FR-003**: O motor MUST ser idempotente: não cria alerta novo se já existe alerta ativo para a mesma (placa, tipo de manutenção, gatilho).
- **FR-004**: Alertas MUST ser permanentes: transição apenas de situação (`ativo` → `resolvido`), nunca exclusão; a tabela é o histórico de notificações do briefing (4.3).
- **FR-005**: Veículo impossível de avaliar MUST gerar alerta `dados_insuficientes` com indicação do que falta.
- **FR-006**: ETL e motor MUST rodar em ciclo agendado único e ordenado (extração → transformação → carga → verificação), com intervalo parametrizado por variável de ambiente.
- **FR-007**: Os gatilhos por km e por tempo MUST ter testes unitários automatizados (critério de aceite do kanban).

### Key Entities

- **Alerta**: placa, limiar que o parametrizou, gatilho (`km` | `tempo` | `dados_insuficientes`), momento de geração, situação (`ativo` | `resolvido`).
- **Limiar (LIMIAR_CONFIG)**: consumido como fonte exclusiva de parametrização (definido na spec 002).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No cenário determinístico da demo (spec 001), depositar o arquivo de gatilho resulta em alerta gerado em no máximo 1 ciclo completo após a ingestão — antes do vencimento real, satisfazendo a métrica binária do briefing.
- **SC-002**: Rodar a verificação 10 vezes seguidas sobre o mesmo estado produz zero alertas duplicados.
- **SC-003**: 100% dos veículos não-avaliáveis aparecem como `dados_insuficientes`; zero veículos silenciosamente ignorados.
- **SC-004**: Alterar o intervalo do ciclo requer zero mudanças de código (somente configuração).
- **SC-005**: Testes unitários dos dois gatilhos passam na suíte do repositório.

## Assumptions

- O agendador embutido no próprio processo (decisão D4 da arquitetura) é suficiente para a PoC; orquestrador dedicado fica documentado como evolução.
- "Resolver" um alerta na PoC pode ser ação simples (atualização de situação via painel ou script); fluxo de atendimento completo está fora de escopo.
- O motor lê exclusivamente o banco consolidado — nunca staging nem arquivos-fonte (princípio central da arquitetura, seção 1).

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v2.md` (seções 5, 7-D4 e 8)
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 2 t1–t4 e t6)
