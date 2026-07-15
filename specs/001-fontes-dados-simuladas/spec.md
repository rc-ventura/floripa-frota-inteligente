# Feature Specification: Fontes de Dados Simuladas (Gerador de Dados)

**Feature Branch**: `feature/001-fontes-dados-simuladas`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Gerar os 4 datasets simulados (abastecimento CSV, multas API/JSON, manutenção XLSX, licenciamento SQLite) com inconsistências propositais e cenário determinístico da demo, conforme arquitetura v1 seção 2."

**Papel responsável**: 🗂️ Dados (geração) + ⚙️ Backend (API fake) · **Fases do kanban**: Fase 0 (task 2), Fase 1 (tasks 1–2), Fase 2 (task 5) · **Depende de**: nenhuma (ponto de partida) · 🔴 demo-crítico

## Clarifications

### Session 2026-07-14

- Q: O gatilho da demo exige um CSV de abastecimento "com km atualizado" (arquitetura §5.2), mas o ERD (§4) lista ABASTECIMENTO sem campo km. Como resolver a contradição? → A: Opção A — o CSV-fonte de abastecimento inclui uma coluna km (leitura do hodômetro no momento do abastecimento, realista em exports de posto); o pipeline usa esse km para atualizar `veiculo.km_atual`. **[Atualizado em 2026-07-14 — ADR-002]** A parte "não persiste o km na tabela consolidada" foi **superseded**: a revisão cruzada com a spec 006 mostrou que, sem a série temporal de hodômetro, o custo/km por período do painel de custos não é calculável. O km agora **é persistido** como `km_hodometro` (nullable) na tabela consolidada `ABASTECIMENTO` — ver `docs/decisoes/ADR-002-persistir-km-hodometro-abastecimento.md` e arquitetura v2 (§4).
- Q: Quais valores concretos de limite_km e limite_dias usar para posicionar os 2 veículos da demo (a arquitetura só dá as antecedências 500/15)? → A: `troca_oleo` para `leve` = 5000 km / 180 dias, antecedências 500/15 (decisão do responsável). Mantidos os 4 tipos de manutenção canônicos da arquitetura (`troca_oleo`, `filtros`, `pneus`, `revisao_geral`), validados contra referenciais reais (SGF/Fortaleza e GeeksforGeeks). Tabela-semente de limiares (9 linhas, 3 tipos de veículo × manutenções relevantes) usada pelo gerador para posicionar os veículos; será formalizada pela spec 002 em `LIMIAR_CONFIG`:

  | tipo_veiculo | tipo_manutencao | limite_km | limite_dias | antecedencia_km | antecedencia_dias |
  |---|---|---|---|---|---|
  | leve | troca_oleo | 5000 | 180 | 500 | 15 |
  | leve | filtros | 5000 | 180 | 500 | 15 |
  | leve | pneus | 40000 | 720 | 2000 | 30 |
  | leve | revisao_geral | 10000 | 365 | 1000 | 30 |
  | ambulancia | troca_oleo | 5000 | 180 | 500 | 15 |
  | ambulancia | revisao_geral | 10000 | 365 | 1000 | 30 |
  | caminhao | troca_oleo | 10000 | 180 | 1000 | 15 |
  | caminhao | pneus | 60000 | 720 | 3000 | 30 |
  | caminhao | revisao_geral | 30000 | 365 | 1500 | 30 |

  *(Tabela atualizada em 2026-07-15: `revisao_geral` de leve e ambulância alinhada ao plano
  padrão de fabricante — 10.000 km/12 meses, o que vier primeiro; ver sessão 2026-07-15 e
  ADR-003 item 9. Caminhões permanecem 30.000 km.)*

  Os 2 veículos da demo nascerão próximos do limiar de `troca_oleo` (leve): um a ~600 km do limite de km (km_desde_ultima ≈ 4400, faltam 600 para 5000; alerta dispara a 4500), outro a ~20 dias do limite de tempo (dias_desde_ultima ≈ 160, faltam 20 para 180; alerta dispara a 165). Demais veículos ficam bem dentro dos limites (sem alertas espúrios).
- Q: Tamanho exato da frota e janela de histórico (a spec dá apenas o intervalo ~30–60 veículos / 6–12 meses)? → A: 40 veículos (≈30 leves, 6 ambulâncias, 4 caminhões) e 8 meses de histórico. Fixa o tamanho para garantir reprodutibilidade (SC-004) e dar ao painel de custos volume agregável, mantendo geração < 1 min (SC-001).
- Q: Como tratar o campo CNH nas multas (tensão entre arquitetura §2 "CNH presente" e spec "sem dado pessoal real")? → A: O JSON de multas **espelha a estrutura do Auto de Infração de Trânsito** (Portaria SENATRAN nº 354/2022, Bloco 3 — Identificação do Condutor), mas com valores **sintéticos não-reais**: campos `placa` (em minúsculas — inconsistência propositada), `data`, `valor`, `situacao`, `condutor` como `COND-NNN` (pseudônimo) e `cnh` com número sintético no formato de CNH (não vinculado a pessoa real). O pipeline, na carga consolidada, **descarta** `cnh` e persiste apenas `condutor_pseudo` na tabela `MULTA` (ERD intacto) — este descarte é o passo de minimização LGPD demonstrável à banca. Base legal: execução de política pública (LGPD art. 7º/23). Uma multa associa-se ao veículo (placa, obrigatória) e ao condutor (nome/CNH/CPF, facultativos no AIT quando identificado); a fonte simulada reflete isso sem dado real.

### Session 2026-07-14 — revisão de realismo (pesquisa web · ADRs 001–003)

Revisão da estrutura de dados proposta contra referenciais reais (padrão de placas, AIT/CTB, calendário DETRAN-SC, sistemas de abastecimento de frota) e contra as demais specs. Decisões registradas em `docs/decisoes/ADR-001..003` e na arquitetura v2:

- Q: O cadastro deve usar só placas no formato antigo `AAA9999`? → A: Não — uma frota em 2026 seria majoritariamente **Mercosul** (`AAA9A99`). O cadastro nasce com ~70% placas Mercosul e ~30% formato antigo; o canônico aceita os dois formatos via regex `^[A-Z]{3}\d[A-Z\d]\d{2}$` (normalização continua: maiúsculas, sem hífen). Ver ADR-001 e arquitetura v2 §2/D7.
- Q: O `valor` das multas pode ser um float sorteado? → A: Não — multas reais têm valores fixos por gravidade (CTB): leve R$ 88,38 · média R$ 130,16 · grave R$ 195,23 · gravíssima R$ 293,47 (e multiplicadores ×2/×3). O gerador sorteia a **gravidade** e deriva o valor; o JSON-fonte ganha `gravidade` e `codigo_infracao` (espelhando o AIT — Portaria SENATRAN 354/2022). A tabela consolidada `MULTA` permanece conforme o ERD: campos extras da fonte são ignorados na carga (mesmo padrão da CNH). Ver ADR-003.
- Q: Como gerar os vencimentos de licenciamento? → A: Coerentes com o **final da placa**, seguindo o calendário do DETRAN-SC (final 1 → 31/03 ... final 0 → 30/12). Além disso, ≥2 registros nascem **vencidos** e ≥2 **vencendo em ≤7 dias**, para o semáforo da spec 005 exibir os três estados (ok/atenção/vencido) sem interferir no cenário determinístico de alertas de manutenção. Ver ADR-003.
- Q: A spec 006 assume "um veículo com custo deliberadamente desproporcional" — quem o gera? → A: Esta spec. Um veículo **leve** nasce deliberadamente caro (mais manutenções corretivas + consumo alto + multas concentradas nele), marcado no cadastro interno (`custo_desproporcional: true`). Multas seguem distribuição enviesada (concentradas em poucos veículos/condutores), não uniforme. Ver ADR-003.
- Q: Litros, km e frequência de abastecimento podem ser sorteados de forma independente? → A: Não — sorteios independentes produzem consumo (km/L) absurdo, visível no painel de custos. O gerador usa um **modelo de consumo**: km/mês por tipo de veículo → litros derivados do consumo típico (leve ~8–14 km/L; ambulância ~6–10 km/L; caminhão ~2–5 km/L) → frequência de abastecimento derivada do tanque. O **hodômetro é monotônico crescente** por veículo e consistente entre CSV de abastecimento e XLSX de manutenção; as exceções são apenas as anomalias propositais, listadas em `INCONSISTENCIAS.md`. Volumes recalibrados: ~1.500 abastecimentos, ~300 manutenções, ~100 multas. Ver ADR-003.
- Q: CNH sintética como 11 dígitos aleatórios garante não-realidade? → A: Quase — ~1% teria dígito verificador válido por acaso. O gerador calcula o DV correto e o **perturba de propósito**, garantindo 100% de CNHs estruturalmente inválidas. Ver ADR-003 e research R2.
- Nota: o limiar `troca_oleo`/`leve` = 5.000 km/180 dias **permanece**, agora com justificativa registrada: frota municipal urbana é caso clássico de **uso severo** (anda-e-para), para o qual a recomendação segue 5.000 km/6 meses mesmo em carros modernos (10.000 km/12 meses vale para uso rodoviário com óleo sintético). A spec 002 deve alinhar sua assumption (que citava ~10.000 km) à tabela-semente desta spec. Ver ADR-003.

### Session 2026-07-15 — realismo da fonte de manutenção (pesquisa web · adendo ao ADR-003)

Revisão da Fonte 3 (XLSX) contra planilhas reais de manutenção de frota, planos de revisão de fabricante e composição real de frotas municipais. Decisões nos itens 7–9 do ADR-003:

- Q: A planilha de manutenção precisa distinguir preventiva de corretiva? → A: Sim — toda planilha real distingue, e o benchmark central do pitch (spec 007: "corretiva custa 3–5× a preventiva") só é demonstrável nos próprios dados com essa coluna. O XLSX-fonte ganha `categoria` (com grafias variadas, como o `tipo`) e a MANUTENCAO consolidada a persiste (arquitetura v2 §4). O gerador calibra corretivas a 3–5× o valor médio das preventivas, concentradas no veículo caro.
- Q: Como tratar veículos em garantia e as revisões programadas do fabricante? → A: O cadastro ganha `ano` distribuído (~2015–2026) e `em_garantia` (`ano ≥ 2023`, ~25% da frota). Veículos em garantia registram revisões programadas nos marcos do fabricante (10.000 km ou 12 meses, o que vier primeiro), com grafias como "Revisão 10.000 km" na aba de terceirizada/concessionária — o pipeline normaliza para `revisao_geral`. O motor não muda: garantia afeta a fonte, não a lógica de limiares.
- Q: Como garantir diversidade de marcas se cada marca tem seu plano? → A: Marcas/modelos vêm de um catálogo real de frota municipal por tipo (leves: Strada, Onix, Spin, Montana, Gol, Saveiro, Kwid; ambulâncias: Master, Ducato; caminhões: VW Delivery, Mercedes Accelo). Os **limiares permanecem por tipo de veículo** — é o que o briefing (4.3) pede, e os planos das marcas populares convergem (10.000 km/12 meses). Plano por modelo fica documentado como evolução: coluna adicional em `LIMIAR_CONFIG` com regra "mais específico vence" (mudança de dados, não de código — nota registrada na spec 002).
- Nota: `revisao_geral` de leve e ambulância na tabela-semente foi alinhada de 20.000 → **10.000 km**/365 dias (padrão de fabricante; o componente de tempo já batia).

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
2. **Given** as multas em JSON, **When** inspecionadas, **Then** contêm placas em minúsculas, condutor pseudonimizado (`COND-NNN`) e um campo `cnh` sintético não-real (espelhando o AIT real — Portaria SENATRAN 354/2022); nenhum nome, CPF ou CNH real existe.
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
- **FR-002**: Todas as fontes MUST referenciar o mesmo cadastro de veículos, com a placa como chave de reconciliação (grafias divergentes entre fontes são esperadas e desejadas). O cadastro MUST misturar os dois formatos vigentes de placa: ~70% Mercosul (`AAA9A99`) e ~30% antigo (`AAA9999`) — ADR-001.
- **FR-003**: Cada fonte MUST conter as inconsistências propositais da tabela da seção 2 da arquitetura, e a lista de inconsistências MUST estar documentada no repositório.
- **FR-004**: Condutores MUST nascer como identificadores sintéticos (`COND-NNN`); nenhum nome, CPF, CNH real ou matrícula real pode existir em qualquer dataset.
- **FR-005**: Dois veículos MUST nascer deterministicamente a ~600 km e ~20 dias dos respectivos limiares, e um arquivo de abastecimento de gatilho MUST ficar pronto para uso na demo. O arquivo de gatilho é um CSV de abastecimento (mesmo formato das demais cargas, incluindo a coluna km/hodômetro) cujo km, ao ser ingerido, faz `veiculo.km_atual` cruzar o limiar de antecedência do veículo da demo.
- **FR-006**: A geração MUST ser reproduzível (semente fixa): mesmas entradas → mesmos dados.
- **FR-007**: Os datasets iniciais MUST ser depositados nos locais convencionados no repositório (seeds e pasta monitorada), conforme estrutura da seção 9 da arquitetura.
- **FR-008**: As multas MUST ser servidas por um endpoint HTTP local que retorna JSON válido (simulando integração com sistema externo, ex.: DETRAN); uma requisição GET simples retorna os dados prontos para o extrator.
- **FR-009**: Um veículo leve MUST nascer com custo de operação deliberadamente desproporcional (corretivas extras + consumo alto + multas concentradas), marcado no cadastro interno, para o comparativo "candidato a renovação" da spec 006 (ADR-003).
- **FR-010**: Os vencimentos de licenciamento MUST ser coerentes com o final da placa (calendário DETRAN-SC) e MUST incluir ≥2 registros vencidos e ≥2 vencendo em ≤7 dias, dando ao semáforo da spec 005 os três estados sem interferir no cenário determinístico de alertas (ADR-003).
- **FR-011**: Os dados MUST ser fisicamente coerentes: hodômetro monotônico crescente por veículo e consistente entre fontes (exceto anomalias propositais documentadas em `INCONSISTENCIAS.md`); litros derivados de um modelo de consumo por tipo de veículo; valores de multa pertencentes à tabela de gravidades do CTB (ADR-003).
- **FR-012**: O cadastro MUST usar um catálogo de marcas/modelos reais de frota municipal por tipo de veículo, com `ano` distribuído (~2015–2026) e ~25% da frota em garantia (`em_garantia`, ano ≥ 2023) (ADR-003 item 8).
- **FR-013**: O XLSX de manutenção MUST incluir a coluna `categoria` (preventiva/corretiva, com grafias variadas) e, para veículos em garantia, registrar revisões programadas nos marcos do fabricante (10.000 km/12 meses) com grafias normalizáveis para `revisao_geral`; corretivas MUST ter valor calibrado a 3–5× o médio das preventivas e concentrar-se no veículo caro (ADR-003 itens 7–8).

### Key Entities

- **Veículo**: placa nos dois formatos vigentes (~70% Mercosul `AAA9A99`, ~30% antigo `AAA9999`; grafias variadas por fonte), tipo (leve, ambulância, caminhão), marca/modelo de catálogo real de frota municipal, ano (~2015–2026; `em_garantia` quando ≥ 2023), secretaria, km atual.
- **Abastecimento**: placa, data, litros, valor, condutor pseudonimizado, **km (hodômetro lido no posto — presente no CSV-fonte e persistido como `km_hodometro` na tabela consolidada, ADR-002; usado pelo pipeline também para atualizar `veiculo.km_atual`)**.
- **Multa**: placa (em minúsculas — inconsistência propositada), data, gravidade e código da infração (espelham o AIT — Portaria SENATRAN 354/2022; fonte-apenas), valor derivado da gravidade (tabela CTB), condutor pseudonimizado (`COND-NNN`), `cnh` sintética com DV propositalmente inválido (descartada na carga consolidada pelo pipeline), situação.
- **Manutenção**: placa, data, tipo (texto livre não padronizado; inclui grafias de revisão programada como "Revisão 10.000 km" para veículos em garantia), categoria (preventiva/corretiva, grafias variadas — persistida no consolidado), km no momento (consistente com o hodômetro dos abastecimentos), valor (corretivas 3–5× as preventivas).
- **Licenciamento**: placa, vencimento coerente com o final da placa — calendário DETRAN-SC (formatos distintos entre registros), situação (inclui vencidos e vencendo).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um único comando produz os 4 datasets em menos de 1 minuto, em qualquer máquina da equipe.
- **SC-002**: 100% das inconsistências listadas na seção 2 da arquitetura estão presentes e documentadas (verificável por checklist manual).
- **SC-003**: Zero ocorrências de dado pessoal real em varredura completa dos datasets.
- **SC-004**: Em 10 regenerações consecutivas, os mesmos 2 veículos da demo aparecem à mesma distância dos limiares (100% reproduzível).
- **SC-005**: Coerência física verificável por teste automatizado: 100% dos valores de multa pertencem à tabela de gravidades do CTB; o consumo derivado (km rodados ÷ litros) de cada veículo fica dentro da faixa plausível do seu tipo (leve 8–14 km/L, ambulância 6–10 km/L, caminhão 2–5 km/L); hodômetro monotônico por veículo, exceto as anomalias propositais documentadas.
- **SC-006**: 100% dos veículos em garantia têm revisão programada registrada dentro do marco vigente do fabricante; a razão de custo médio corretiva ÷ preventiva do dataset fica entre 3× e 5× (verificável por teste — é o insumo da análise de impacto econômico da spec 007).

## Assumptions

- Não haverá amostra de dados reais da organização (Fase 0, task 2); os dados simulados com estrutura representativa são a decisão formalizada — se uma amostra real surgir, ela entra como fonte adicional, não substituta.
- Escala assumida: 40 veículos (≈30 leves, 6 ambulâncias, 4 caminhões) e 8 meses de histórico, suficiente para custos agregados e pequeno o bastante para a demo (decisão 2026-07-14, ver `## Clarifications`).
- Os limiares usados para posicionar os veículos da demo são os definidos na spec `002-modelo-dados-banco` (LIMIAR_CONFIG); as duas frentes devem combinar os valores antes de fechar. **(Resolvido em 2026-07-14: ver `## Clarifications` — tabela-semente de 9 linhas adotada, com `troca_oleo`/`leve` = 5000 km / 180 dias, antecedências 500/15; a spec 002 formalizará a mesma tabela em `LIMIAR_CONFIG`.)**
- A mini-API de multas faz parte desta spec (é uma fonte simulada); o consumo dela é responsabilidade da spec `003-pipeline-etl`.

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v2.md` (seções 2, 4, 5.2 e 9)
- ADRs: `docs/decisoes/ADR-001-placa-canonica-dois-formatos.md` · `docs/decisoes/ADR-002-persistir-km-hodometro-abastecimento.md` · `docs/decisoes/ADR-003-calibracao-realismo-fontes-simuladas.md` (com os links da pesquisa de realismo)
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 0 t2, Fase 1 t1, Fase 2 t5)
