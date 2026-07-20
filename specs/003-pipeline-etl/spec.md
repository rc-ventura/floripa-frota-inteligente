# Feature Specification: Pipeline ETL de Integração das Fontes

**Feature Branch**: `feature/003-pipeline-etl`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Pipeline em três estágios (Extract → Validate & Transform → Load) que integra as 4 fontes heterogêneas no banco consolidado, com regras de qualidade, log de rejeições e carga idempotente, conforme arquitetura v1 seção 3."

**Papel responsável**: 🗂️ Dados (extração/transformação) + ⚙️ Backend (carga idempotente) · **Fases do kanban**: Fase 1 (tasks 4–10) · **Depende de**: 001 (dados existirem), 002 (esquema existir) · 🔴 demo-crítico

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extração bruta com rastreabilidade (Priority: P1)

Como gestor auditando o painel, preciso que todo dado exibido seja rastreável até a fonte e a carga que o trouxeram, o que exige que cada extrator deposite os dados brutos, sem transformação, no staging com carimbo de carga e origem.

**Why this priority**: Rastreabilidade da origem é exigência do briefing (4.1) e pré-condição de tudo: sem extração não há transformação nem carga. O extrator de abastecimento (pasta monitorada) é demo-crítico — é por ele que o alerta ao vivo entra.

**Independent Test**: Depositar/expor dados em cada uma das 4 fontes, rodar a extração e verificar staging populado com dado bruto intacto + carimbo de carga + origem.

**Acceptance Scenarios**:

1. **Given** um CSV novo na pasta monitorada, **When** o ciclo de extração roda, **Then** o staging de abastecimento recebe os registros brutos (sem qualquer normalização) com data/hora da carga e nome do arquivo de origem.
2. **Given** o endpoint de multas disponível, **When** o extrator o consome, **Then** o staging de multas recebe os registros com identificação do endpoint como origem.
3. **Given** a planilha de manutenção com múltiplas abas, **When** extraída, **Then** todas as abas relevantes são lidas para o staging.
4. **Given** a base legada de licenciamento, **When** consultada, **Then** os registros chegam ao staging, incluindo os duplicados (deduplicação é papel da transformação, não da extração).

---

### User Story 2 - Qualidade: normalizar o que dá, rejeitar com motivo o que não dá (Priority: P1)

Como membro da banca avaliando o tratamento de inconsistências, preciso ver dados heterogêneos convergindo para um padrão canônico e registros inválidos indo para um log de qualidade com motivo explícito — nunca descartados silenciosamente.

**Why this priority**: É o coração do desafio de integração (risco nº 1 do briefing) e evidência direta para a banca; sem placa canônica não existe reconciliação entre fontes.

**Independent Test**: Alimentar o staging com os dados propositalmente inconsistentes da spec 001 e verificar consolidado limpo + log_qualidade com os rejeitados e motivos.

**Acceptance Scenarios**:

1. **Given** placas grafadas como `ABC-1D23`, `abc1d23` e `ABC 1D23` em fontes distintas (idem para o formato antigo: `XYZ-1234`, `xyz1234`), **When** transformadas, **Then** todas viram o canônico (`ABC1D23` / `XYZ1234`) e reconciliam no mesmo veículo.
2. **Given** datas em `dd/mm/aaaa`, `aaaa-mm-dd` e serial de planilha, **When** transformadas, **Then** todas viram data válida única; datas impossíveis de interpretar geram rejeição com motivo `data_ausente`/`data_invalida`.
3. **Given** litros/valores com vírgula decimal, **When** transformados, **Then** viram numérico correto.
4. **Given** tipos de manutenção como "troca de oleo" e "Troca Óleo", **When** transformados, **Then** convergem para vocabulário padronizado (`troca_oleo`).
5. **Given** registros duplicados por chave natural (placa + data + tipo), **When** transformados, **Then** apenas um segue para o consolidado e o duplicado vai para `log_qualidade` com motivo `duplicado`.
6. **Given** um registro com placa não normalizável, **When** transformado, **Then** vai para `log_qualidade` com motivo `placa_invalida` — e o restante do lote segue normalmente.

---

### User Story 3 - Carga idempotente (Priority: P1)

Como operador do agendamento automático, preciso que rodar o pipeline N vezes sobre os mesmos dados produza exatamente o mesmo estado no banco, para que o ciclo agendado funcione sem supervisão e sem duplicar nada.

**Why this priority**: Requisito para o agendamento automático da demo (o ciclo roda a cada 1–2 min sobre fontes que quase nunca mudam); tarefa demo-crítica do kanban com critério de teste explícito.

**Independent Test**: Rodar o pipeline duas vezes sobre os mesmos dados e comparar contagens e conteúdo das tabelas consolidadas.

**Acceptance Scenarios**:

1. **Given** um ciclo completo executado, **When** o pipeline roda de novo sem dados novos, **Then** nenhuma tabela consolidada muda (mesmas contagens, mesmos conteúdos).
2. **Given** um arquivo já processado e um arquivo novo na pasta, **When** o ciclo roda, **Then** apenas os dados novos são incorporados.

---

### User Story 4 - Resiliência por fonte (Priority: P2)

Como operador, preciso que a falha de uma fonte (endpoint fora do ar, arquivo corrompido) não derrube o ciclo: a falha é registrada e as demais fontes seguem.

**Why this priority**: Robustez é parte da narrativa de avaliação, mas o caminho feliz (US1–US3) precisa existir primeiro.

**Independent Test**: Derrubar o endpoint de multas e rodar o ciclo; verificar que abastecimento, manutenção e licenciamento processam normalmente e a falha fica registrada.

**Acceptance Scenarios**:

1. **Given** o endpoint de multas indisponível, **When** o ciclo roda, **Then** as outras 3 fontes são processadas e a falha da fonte fica registrada para diagnóstico.

### Edge Cases

- Arquivo depositado duas vezes (mesmo nome ou renomeado, mesmo conteúdo): não duplica consolidado.
- Arquivo parcialmente corrompido: linhas válidas entram, inválidas vão para `log_qualidade` — nunca tudo-ou-nada.
- Planilha com aba inesperada ou colunas fora de ordem: extrator não quebra o ciclo.
- Registro de evento para placa que não existe no cadastro de veículos: comportamento definido (rejeição com motivo próprio), não erro silencioso.
- Staging crescendo a cada carga: reprocessar staging antigo não pode reintroduzir duplicatas (idempotência de ponta a ponta).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O pipeline MUST ter um extrator por fonte, cada um lendo seu formato nativo (CSV em pasta monitorada, endpoint JSON, XLSX multi-abas, base SQL legada) e gravando dado bruto no staging correspondente.
- **FR-002**: Todo registro de staging MUST carregar carimbo de data/hora da carga e identificação do arquivo/endpoint de origem (rastreabilidade, briefing 4.1).
- **FR-003**: A transformação MUST normalizar placa para o canônico (maiúsculas, sem hífen/espaço; formatos antigo `AAA9999` e Mercosul `AAA9A99`, validados pela regex `^[A-Z]{3}\d[A-Z\d]\d{2}$` — ADR-001), interpretar datas em múltiplos formatos (incluindo serial de planilha), converter decimais com vírgula e padronizar vocabulário de tipos de manutenção — incluindo grafias de revisão programada (ex.: "Revisão 10.000 km" → `revisao_geral`) e a coluna `categoria` para `preventiva` | `corretiva` (ADR-003 itens 7–8).
- **FR-004**: A transformação MUST deduplicar cada fonte pela chave natural da sua tabela consolidada (contrato da spec 002 — ex.: `placa + data + tipo` em manutenção; `placa + data + km` em abastecimento; `placa + data + valor + condutor` em multas; `placa` mantendo o vencimento mais recente em licenciamento).
- **FR-005**: Registro rejeitado MUST ir para `log_qualidade` com o registro bruto e o motivo (`placa_invalida`, `data_ausente`, `duplicado`, ...); nenhuma rejeição pode ser silenciosa.
- **FR-006**: A carga MUST ser idempotente (upsert): executar o pipeline N vezes sobre os mesmos dados resulta no mesmo estado consolidado, comprovado por teste automatizado.
- **FR-007**: Cada extrator MUST rodar isolado: falha em uma fonte não interrompe o processamento das demais e fica registrada.
- **FR-008**: Um ciclo completo (E→T→L das 4 fontes) MUST ser executável por um único ponto de entrada, invocável pelo agendador (spec 004).
- **FR-009**: As regras de qualidade e a origem de cada dado MUST estar documentadas no repositório (exigência do briefing 4.1 — task 10 da Fase 1, papel Docs).
- **FR-010**: A carga de abastecimento MUST persistir a leitura de hodômetro do CSV-fonte como `km_hodometro` no ABASTECIMENTO consolidado e atualizar `veiculo.km_atual` com a maior leitura válida da placa (ADR-002). Leitura ausente não invalida o registro (coluna nullable); leitura decrescente em relação ao histórico é caso de km não confiável (tratado pelo motor — spec 004).
- **FR-011**: A carga de multas MUST persistir apenas os campos do ERD (`placa`, `data`, `valor`, `condutor_pseudo`, `situacao`, `fonte_origem`); os campos fonte-apenas `cnh`, `gravidade` e `codigo_infracao` MUST ser descartados na consolidação (minimização LGPD demonstrável + ADR-003).

### Key Entities

- **Registro de staging**: dado bruto + carimbo de carga + fonte de origem.
- **Registro consolidado**: dado normalizado nas tabelas do ERD (spec 002), com `fonte_origem`.
- **Rejeição (log_qualidade)**: registro bruto + motivo + momento da carga.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Duas execuções consecutivas sobre os mesmos dados produzem estado idêntico no consolidado (0 duplicatas) — verificado por teste automatizado.
- **SC-002**: 100% dos registros propositalmente inválidos da spec 001 aparecem em `log_qualidade` com motivo; 0 rejeições silenciosas.
- **SC-003**: 100% dos registros consolidados são rastreáveis à carga e à fonte de origem.
- **SC-004**: Um ciclo completo das 4 fontes termina em menos de 1 minuto com o volume da PoC (compatível com o ciclo de 1–2 min da demo).
- **SC-005**: Com uma fonte indisponível, as outras 3 processam 100% dos seus dados no mesmo ciclo.

## Assumptions

- Os formatos e inconsistências de entrada são exatamente os produzidos pela spec 001; inconsistência nova descoberta vira regra de qualidade nova + registro na documentação.
- O disparo é por ciclo agendado (batch), não streaming nem evento de arquivo (decisão 3.2 da arquitetura); gatilho por evento fica documentado como evolução.
- Arquivos já processados permanecem na pasta (o controle de "já visto" é do pipeline), preservando o cenário da demo de simplesmente depositar um CSV novo.
- O cadastro canônico da frota (`data/seeds/veiculos.json`, referência interna da spec 001) é carregado pelo pipeline **antes** das 4 fontes de eventos — as FKs e o `tipo_veiculo` (NOT NULL) dependem dele; evento cuja placa canônica não existe no cadastro é rejeitado com motivo `veiculo_desconhecido`.

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v2.md` (seções 3, 4, 8 e 9)
- ADRs: `docs/decisoes/ADR-001-placa-canonica-dois-formatos.md` · `docs/decisoes/ADR-002-persistir-km-hodometro-abastecimento.md` · `docs/decisoes/ADR-003-calibracao-realismo-fontes-simuladas.md`
- Contratos das fontes: `specs/001-fontes-dados-simuladas/contracts/` (formatos de arquivo e API de multas)
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 1 t4–t10)
