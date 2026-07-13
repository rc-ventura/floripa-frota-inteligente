# Feature Specification: Fontes de Dados Simuladas (Gerador de Dados)

**Feature Branch**: `feature/001-fontes-dados-simuladas`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Gerar os 4 datasets simulados (abastecimento CSV, multas API/JSON, manutenção XLSX, licenciamento SQLite) com inconsistências propositais e cenário determinístico da demo, conforme arquitetura v1 seção 2."

**Papel responsável**: 🗂️ Dados (geração) + ⚙️ Backend (API fake) · **Fases do kanban**: Fase 0 (task 2), Fase 1 (tasks 1–2), Fase 2 (task 5) · **Depende de**: nenhuma (ponto de partida) · 🔴 demo-crítico

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Quatro fontes heterogêneas prontas para o pipeline (Priority: P1)

Como membro da equipe (dados, backend ou frontend), preciso de quatro conjuntos de dados simulados — abastecimento, multas, manutenção e licenciamento — cada um em formato e padrão diferentes, para que todas as demais frentes (pipeline, motor, dashboard) possam ser desenvolvidas em paralelo sem depender de dados reais da Prefeitura.

**Why this priority**: Nada mais no projeto anda sem dados. É a primeira entrega da Fase 1 e desbloqueia todo o time.

**Independent Test**: Executar o gerador em um único comando e verificar que os 4 artefatos existem nos locais combinados, cada um no seu formato, referenciando o mesmo conjunto de veículos.

**Acceptance Scenarios**:

1. **Given** um repositório recém-clonado, **When** o gerador é executado, **Then** são produzidos: um CSV de abastecimento, uma coleção de multas consumível via endpoint JSON, uma planilha XLSX multi-abas de manutenção e uma base SQLite de licenciamento.
2. **Given** os 4 datasets gerados, **When** as placas são comparadas entre fontes, **Then** todas as fontes referenciam o mesmo conjunto de veículos (a placa é a chave de reconciliação, ainda que grafada de formas diferentes em cada fonte).

---

### User Story 2 - Inconsistências propositais documentadas (Priority: P1)

Como responsável pelo pipeline, preciso que cada fonte contenha as inconsistências previstas na arquitetura (seção 2), documentadas, para que as regras de qualidade tenham o que tratar e a banca veja evidência do tratamento de dados reais.

**Why this priority**: A heterogeneidade das fontes é o risco nº 1 do briefing; sem inconsistências controladas não há como demonstrar o tratamento delas.

**Independent Test**: Inspecionar cada dataset e conferir, item a item, a lista de inconsistências documentada.

**Acceptance Scenarios**:

1. **Given** o CSV de abastecimento, **When** inspecionado, **Then** contém placas com e sem hífen, datas em `dd/mm/aaaa` e `aaaa-mm-dd`, e litros com vírgula decimal.
2. **Given** as multas em JSON, **When** inspecionadas, **Then** contêm placas em minúsculas e condutor apenas pseudonimizado.
3. **Given** o XLSX de manutenção, **When** inspecionado, **Then** contém registros com km ausente e tipos de manutenção sem padronização de texto (ex.: "troca de oleo", "Troca Óleo").
4. **Given** a base de licenciamento, **When** inspecionada, **Then** contém placas duplicadas e vencimentos em formatos distintos.

---

### User Story 3 - Cenário determinístico da demo (Priority: P2)

Como apresentador da demo, preciso que exatamente dois veículos nasçam próximos dos limiares (~600 km e ~20 dias) e que exista um arquivo de abastecimento "de gatilho" pronto para depositar ao vivo, para que o alerta dispare de forma reproduzível durante a apresentação.

**Why this priority**: É o caminho para a métrica binária de sucesso do briefing (alerta antes do vencimento), mas depende da US1 existir.

**Independent Test**: Regenerar os dados N vezes e confirmar que os mesmos dois veículos ficam sempre à mesma distância dos limiares; depositar o arquivo de gatilho e conferir que ele cruza o limiar de antecedência.

**Acceptance Scenarios**:

1. **Given** os dados gerados, **When** verificados os dois veículos marcados para a demo, **Then** um está a ~600 km do limite de km e outro a ~20 dias do limite de tempo (dentro da janela de antecedência ainda não cruzada).
2. **Given** o arquivo de gatilho preparado, **When** ingerido pelo pipeline, **Then** o km atualizado cruza o limiar de antecedência do veículo da demo.

---

### User Story 4 - Nenhum dado pessoal real (Priority: P2)

Como responsável por conformidade, preciso que nenhum nome real de servidor exista no dataset — condutores nascem como identificadores sintéticos (`COND-042`) — para que a pseudonimização LGPD seja de origem, não correção posterior.

**Why this priority**: O briefing trata ausência de estratégia de proteção de dados como possível critério de desclassificação.

**Independent Test**: Varrer todos os datasets gerados buscando qualquer campo de identificação pessoal em claro.

**Acceptance Scenarios**:

1. **Given** qualquer dataset gerado, **When** varrido por campos de condutor, **Then** só existem identificadores no padrão `COND-NNN`, sem nomes, CPFs ou matrículas reais.

### Edge Cases

- Regeneração: rodar o gerador duas vezes deve produzir resultado idêntico (semente fixa) ou claramente versionado — nunca um cenário de demo diferente a cada execução.
- Volume: dados suficientes para o painel de custos ter o que agregar (histórico de meses), mas pequenos o bastante para ciclos de 1–2 min na demo.
- As inconsistências não podem tornar um veículo da demo inválido: os dois veículos "no gatilho" precisam passar pelas regras de qualidade.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O gerador MUST produzir, em um único comando, os 4 datasets: abastecimento (CSV), multas (JSON servível por endpoint), manutenção (XLSX multi-abas) e licenciamento (base SQL local).
- **FR-002**: Todas as fontes MUST referenciar o mesmo cadastro de veículos, com a placa como chave de reconciliação (grafias divergentes entre fontes são esperadas e desejadas).
- **FR-003**: Cada fonte MUST conter as inconsistências propositais da tabela da seção 2 da arquitetura, e a lista de inconsistências MUST estar documentada no repositório.
- **FR-004**: Condutores MUST nascer como identificadores sintéticos (`COND-NNN`); nenhum nome, CPF, CNH real ou matrícula real pode existir em qualquer dataset.
- **FR-005**: Dois veículos MUST nascer deterministicamente a ~600 km e ~20 dias dos respectivos limiares, e um arquivo de abastecimento de gatilho MUST ficar pronto para uso na demo.
- **FR-006**: A geração MUST ser reproduzível (semente fixa): mesmas entradas → mesmos dados.
- **FR-007**: Os datasets iniciais MUST ser depositados nos locais convencionados no repositório (seeds e pasta monitorada), conforme estrutura da seção 9 da arquitetura.
- **FR-008**: As multas MUST ser servidas por um endpoint HTTP local que retorna JSON válido (simulando integração com sistema externo, ex.: DETRAN); uma requisição GET simples retorna os dados prontos para o extrator.

### Key Entities

- **Veículo**: placa (grafias variadas por fonte), tipo (leve, ambulância, caminhão), modelo, ano, secretaria, km atual.
- **Abastecimento**: placa, data, litros, valor, condutor pseudonimizado.
- **Multa**: placa, data, valor, condutor pseudonimizado, situação.
- **Manutenção**: placa, data, tipo (texto livre não padronizado), km no momento, valor.
- **Licenciamento**: placa, vencimento (formatos distintos), situação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um único comando produz os 4 datasets em menos de 1 minuto, em qualquer máquina da equipe.
- **SC-002**: 100% das inconsistências listadas na seção 2 da arquitetura estão presentes e documentadas (verificável por checklist manual).
- **SC-003**: Zero ocorrências de dado pessoal real em varredura completa dos datasets.
- **SC-004**: Em 10 regenerações consecutivas, os mesmos 2 veículos da demo aparecem à mesma distância dos limiares (100% reproduzível).

## Assumptions

- Não haverá amostra de dados reais da organização (Fase 0, task 2); os dados simulados com estrutura representativa são a decisão formalizada — se uma amostra real surgir, ela entra como fonte adicional, não substituta.
- Escala assumida: ~30–60 veículos e 6–12 meses de histórico, suficiente para custos agregados e pequeno o bastante para a demo.
- Os limiares usados para posicionar os veículos da demo são os definidos na spec `002-modelo-dados-banco` (LIMIAR_CONFIG); as duas frentes devem combinar os valores antes de fechar.
- A mini-API de multas faz parte desta spec (é uma fonte simulada); o consumo dela é responsabilidade da spec `003-pipeline-etl`.

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v1.md` (seções 2, 5.2 e 9)
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 0 t2, Fase 1 t1, Fase 2 t5)
