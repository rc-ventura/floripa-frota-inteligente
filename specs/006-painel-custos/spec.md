# Feature Specification: Painel de Custos da Frota

**Feature Branch**: `feature/006-painel-custos`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Visão de custos do dashboard: gastos por veículo/período/tipo de despesa, comparativo entre veículos com destaque para custo desproporcional, indicadores marcados como derivados ou calculados e agregados exportáveis, conforme arquitetura v1 seções 6 e 10."

**Papel responsável**: 🖥️ Frontend (+ 📄 Docs na marcação de indicadores) · **Fases do kanban**: Fase 3a (tasks 1–3) · **Depende de**: 002, 003 (dados consolidados de gastos); complementa 005 (mesmo dashboard) · Prioridade normal

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gastos consolidados por veículo, período e tipo (Priority: P1)

Como gestor da frota, quero ver quanto cada veículo custa — combustível, manutenção e multas — filtrado por período, para finalmente enxergar o custo total de operação que hoje está espalhado em quatro sistemas.

**Why this priority**: É o resultado nº 3 do briefing (painel de custos); é a base sobre a qual o comparativo (US2) se apoia.

**Independent Test**: Popular o banco com gastos conhecidos e conferir os totais por veículo, período e tipo contra soma manual.

**Acceptance Scenarios**:

1. **Given** veículos com abastecimentos, manutenções e multas carregados, **When** a visão de custos é aberta, **Then** exibe gasto por veículo decomposto por tipo de despesa (combustível, manutenção, multas).
2. **Given** um filtro de período aplicado, **When** os totais são recalculados, **Then** refletem somente os eventos do período e batem com a soma dos registros consolidados.

---

### User Story 2 - Comparativo: candidato a renovação (Priority: P2)

Como gestor, quero comparar veículos entre si e ver destacado aquele com custo de operação desproporcional, para fundamentar decisões de renovação de frota com dados.

**Why this priority**: É o insight que transforma o painel de relatório em ferramenta de decisão — argumento central do pitch; depende da consolidação (US1).

**Independent Test**: Incluir nos dados simulados um veículo deliberadamente caro e verificar que o painel o destaca.

**Acceptance Scenarios**:

1. **Given** veículos com custos distintos, **When** o comparativo é aberto, **Then** pelo menos uma visualização compara veículos e destaca custo desproporcional (ex.: custo por km ou custo total muito acima dos pares da mesma categoria).
2. **Given** o veículo destacado, **When** inspecionado, **Then** é possível ver a composição do custo que o tornou candidato a renovação.

---

### User Story 3 - Indicador transparente: derivado ou calculado (Priority: P3)

Como membro da banca (ou auditor), quero saber, para cada indicador, se ele vem direto das fontes ou se é calculado pela plataforma, atendendo a exigência de documentação do briefing.

**Why this priority**: Exigência explícita do briefing, mas é uma camada de anotação sobre indicadores que precisam existir primeiro.

**Independent Test**: Percorrer todos os indicadores da visão de custos e conferir a marcação.

**Acceptance Scenarios**:

1. **Given** qualquer indicador exibido na visão de custos, **When** consultada sua nota/tooltip, **Then** informa se é derivado direto das fontes ou calculado pela plataforma (e, se calculado, qual a regra).

### Edge Cases

- Veículo sem nenhum gasto no período: aparece zerado, não desaparece do comparativo.
- Custo por km quando o km rodado no período é zero ou não confiável: indicador exibe "não calculável" em vez de dividir por zero ou mostrar número enganoso.
- Período sem dados (ex.: filtro antes do início do histórico): estado vazio claro.
- Comparativo entre categorias diferentes (ambulância × carro leve): comparação deve ser dentro da mesma categoria ou explicitamente sinalizada — evitar conclusão injusta.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A visão de custos MUST consolidar gastos por veículo, por período e por tipo de despesa (combustível, manutenção, multas).
- **FR-002**: MUST existir pelo menos um comparativo entre veículos destacando custo de operação desproporcional (candidato a renovação), com a composição do custo acessível.
- **FR-003**: Todo indicador MUST informar se é derivado direto das fontes ou calculado pela plataforma (marcação registrada também na documentação — task 3, papel Docs).
- **FR-004**: Na visão pública (toggle da spec 005), os agregados de custo MUST ser exportáveis em formato aberto tabular (CSV) para portal de transparência (LAI — arquitetura seção 10).
- **FR-005**: A visão de custos MUST respeitar o filtro Gestor/Pública: nenhum dado individualizável de condutor em agregados públicos.
- **FR-006**: Gráficos concentram-se nesta visão (diretriz da arquitetura seção 6): MUST haver visualização gráfica onde ela agrega análise real (ex.: composição e comparativo), mantendo "dado correto e claro > gráfico elaborado".

### Key Entities

- **Gasto consolidado**: agregação dos eventos de abastecimento, manutenção e multa por veículo/período/tipo.
- **Indicador**: métrica exibida, com origem declarada (derivado × calculado) e regra de cálculo quando aplicável.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Totais exibidos batem 100% com a soma dos registros consolidados do banco (verificável por consulta independente).
- **SC-002**: Um gestor identifica o veículo mais caro da frota (e sua composição de custo) em menos de 30 segundos na visão de custos.
- **SC-003**: 100% dos indicadores da visão de custos possuem marcação derivado/calculado.
- **SC-004**: Exportação pública gera arquivo tabular válido contendo apenas agregados (zero campos de condutor).

## Assumptions

- Os dados simulados (spec 001) incluem exatamente um veículo leve com custo deliberadamente desproporcional para o comparativo ter o que destacar — garantido pelo FR-009 da spec 001 (ADR-003), marcado no cadastro do gerador.
- "Custo desproporcional" na PoC = destaque visual baseado em regra simples e explicável (ex.: custo/km acima de X% da mediana da categoria); modelos sofisticados ficam como evolução.
- O km rodado por período (base do custo/km e do consumo km/L) é derivável da série `km_hodometro` do ABASTECIMENTO consolidado (max−min das leituras da placa no período — ADR-002); quando não houver ≥2 leituras válidas no período, vale o edge case "não calculável".
- Multas entram no custo do veículo (visão de gestão de frota), ainda que administrativamente possam ser repassadas ao condutor — decisão de escopo da PoC, anotada na marcação do indicador.

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v2.md` (seções 4, 6 e 10)
- ADR: `docs/decisoes/ADR-002-persistir-km-hodometro-abastecimento.md` (viabiliza custo/km por período)
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 3a t1–t3)
