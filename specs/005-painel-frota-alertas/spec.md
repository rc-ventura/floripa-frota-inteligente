# Feature Specification: Painel da Frota e de Alertas

**Feature Branch**: `feature/005-painel-frota-alertas`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Dashboard com visão da situação da frota (semáforo por urgência), visão de alertas ativos + histórico, drill-down por veículo, toggle Gestor/Pública (LGPD×LAI) e auto-refresh, conforme arquitetura v1 seção 6."

**Papel responsável**: 🖥️ Frontend (+ 📄 Docs no teste de usabilidade) · **Fases do kanban**: Fase 3 (tasks 1–6) · **Depende de**: 002 (esquema), 003 (dados consolidados), 004 (alertas) · 🔴 demo-crítico · 🟡 compliance (toggle)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - "O que vence esta semana?" sem nenhum clique (Priority: P1)

Como gestor da frota, ao abrir o painel quero ver imediatamente a lista de veículos com semáforo (ok / atenção / vencido) ordenada por urgência, respondendo "o que vence esta semana?" sem precisar clicar em nada.

**Why this priority**: É o resultado nº 1 do briefing (frota unificada em painel único) e a diretriz de interface "urgência primeiro"; é a primeira tela da demo.

**Independent Test**: Popular o banco com veículos em situações variadas, abrir o painel e verificar a tela inicial sem interação.

**Acceptance Scenarios**:

1. **Given** veículos em situações ok, atenção e vencido, **When** o painel é aberto, **Then** a tela inicial lista os veículos com semáforo, ordenados do mais urgente para o menos urgente, sem exigir cliques.
2. **Given** um veículo com licenciamento ou manutenção vencendo nos próximos 7 dias, **When** o painel é aberto, **Then** ele aparece destacado no topo da lista.

---

### User Story 2 - Alertas ativos em destaque + histórico (Priority: P1)

Como gestor, quero ver os alertas ativos em destaque — com o gatilho (km ou tempo) e o limiar configurado que os originou — e consultar o histórico de notificações.

**Why this priority**: É a materialização visual do motor de alertas (resultado nº 2 do briefing) e a tela onde o alerta da demo "aparece ao vivo".

**Independent Test**: Gerar alertas via motor (spec 004) e verificar exibição, com gatilho e limiar, mais o histórico de resolvidos.

**Acceptance Scenarios**:

1. **Given** alertas ativos no banco, **When** a visão de alertas é aberta, **Then** cada alerta exibe placa, gatilho (km/tempo/dados insuficientes) e o limiar configurado que o parametrizou.
2. **Given** alertas resolvidos, **When** o histórico é consultado, **Then** as notificações passadas aparecem com sua situação.

---

### User Story 3 - Toggle Gestor/Pública (Priority: P1)

Como responsável por conformidade, preciso de um seletor Gestor/Pública em que a visão pública oculta todo campo pseudonimizado de condutor e exibe apenas agregados — materializando na demo a resolução da tensão LGPD × LAI.

**Why this priority**: Task de compliance do kanban; o briefing trata proteção de dados como possível critério de desclassificação.

**Independent Test**: Alternar o seletor e varrer a interface procurando qualquer campo de condutor na visão pública.

**Acceptance Scenarios**:

1. **Given** o painel na visão Gestor, **When** alternado para Pública, **Then** nenhum campo `condutor_pseudo` (nem qualquer dado individualizável de condutor) é exibido em nenhuma tela.
2. **Given** a visão Pública ativa, **When** navegada, **Then** apenas informações agregadas (por veículo, categoria, período) são exibidas.

---

### User Story 4 - Drill-down por veículo (Priority: P2)

Como gestor, quero clicar em um veículo e ver seu histórico completo — abastecimentos, manutenções, multas e licenciamento — em um só lugar.

**Why this priority**: Completa a visão unificada, mas a demo funciona sem ele; prioridade normal no kanban.

**Independent Test**: Selecionar uma placa e conferir os quatro históricos contra o banco.

**Acceptance Scenarios**:

1. **Given** um veículo com eventos nas quatro dimensões, **When** o gestor faz drill-down pela placa, **Then** vê os históricos de abastecimento, manutenção, multas e licenciamento daquele veículo.

---

### User Story 5 - Alerta aparecendo "ao vivo" (auto-refresh) (Priority: P1)

Como apresentador da demo, preciso que o painel se atualize sozinho (~30s) para que o alerta gerado durante a apresentação apareça na tela sem que ninguém toque no teclado.

**Why this priority**: Demo-crítico: é o efeito visual que fecha o roteiro do disparo ao vivo.

**Independent Test**: Com o painel aberto, inserir um alerta no banco e cronometrar até ele aparecer sem interação.

**Acceptance Scenarios**:

1. **Given** o painel aberto e um alerta novo gerado, **When** decorre o intervalo de atualização (~30s), **Then** o alerta aparece na tela sem qualquer interação manual.

### Edge Cases

- Banco vazio (primeiro boot): painel mostra estado vazio compreensível, não erro.
- Veículo sem dados suficientes para o semáforo: aparece com indicação explícita (coerente com `dados_insuficientes` da spec 004), nunca some da lista.
- Muitos alertas simultâneos: a ordenação por urgência continua legível (o topo continua respondendo "o que é mais urgente").
- Alternância de visão no meio da navegação: a visão pública não pode "vazar" dado de condutor em nenhuma rota/tela intermediária, tooltip ou exportação.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A tela inicial MUST listar todos os veículos com semáforo ok/atenção/vencido, ordenados por urgência, sem exigir interação.
- **FR-002**: A visão de alertas MUST destacar alertas ativos e exibir, para cada um: placa, tipo de gatilho e limiar configurado; e MUST oferecer o histórico de notificações.
- **FR-003**: O painel MUST oferecer drill-down por veículo com os históricos de abastecimento, manutenção, multas e licenciamento.
- **FR-004**: O seletor Gestor/Pública MUST ocultar, na visão pública, todos os campos pseudonimizados de condutor e exibir apenas agregados.
- **FR-005**: O painel MUST se atualizar automaticamente (~30 segundos) sem interação do usuário.
- **FR-006**: O painel MUST ler exclusivamente o banco consolidado — nunca arquivos-fonte (princípio central da arquitetura).
- **FR-007**: Cada indicador exibido MUST informar (tooltip ou nota) se é derivado direto das fontes ou calculado pela plataforma (exigência de documentação do briefing; entra aqui e na spec 006).
- **FR-008**: Um teste de usabilidade com 1–2 pessoas de fora do time (simulando gestor público) MUST ser realizado e os ajustes registrados no repositório (task 6 da Fase 3).

### Key Entities

- **Situação do veículo (semáforo)**: derivada de licenciamento, alertas e limiares — regra de derivação deve ficar explícita na documentação do painel.
- **Alerta exibido**: projeção da tabela de alertas (spec 004) com o limiar associado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um gestor identifica "o que vence esta semana" em menos de 10 segundos após abrir o painel, sem nenhum clique.
- **SC-002**: Um alerta novo aparece na tela em no máximo 60 segundos após ser gerado, sem interação manual.
- **SC-003**: Na visão pública, zero campos de condutor visíveis em varredura completa de todas as telas.
- **SC-004**: Teste de usabilidade com ≥1 pessoa externa concluído e ajustes registrados no repositório.

## Assumptions

- "Urgência" combina: vencido > em janela de antecedência (atenção) > ok; empates ordenados por data/km mais próximos do limite — regra final documentada junto ao painel.
- Os dados simulados garantem os três estados do semáforo já na primeira carga: a spec 001 (FR-010, ADR-003) gera ≥2 licenciamentos vencidos e ≥2 vencendo em ≤7 dias, fora dos 2 veículos do cenário de alertas — a tela inicial da demo nunca nasce monocromática.
- A ação de "resolver" alerta pelo painel é desejável, mas pode ser simplificada na PoC (ver assumption equivalente na spec 004).
- Simplicidade sobre sofisticação (briefing 4.2): tabelas e semáforos claros valem mais que gráficos nesta parte; gráficos concentram-se na spec 006.

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v2.md` (seções 6 e 10)
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 3 t1–t6)
