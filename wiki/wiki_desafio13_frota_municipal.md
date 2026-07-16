# Wiki do Projeto — Desafio 13: Gestão Inteligente da Frota Municipal

**1ª Jornada Incubintech de Inovação Aberta** · Demandante: Secretaria Municipal de Administração de Florianópolis
**Última atualização deste índice:** 14/07/2026

Esta página é o ponto de entrada único do projeto: reúne, resume e conecta todos os documentos produzidos até aqui. Quem chegar agora à equipe deve conseguir se situar lendo só esta página, e ir aos documentos originais apenas para o detalhe que precisar.

> **Nota de manutenção:** esta wiki referencia os arquivos pelo nome, assumindo que todos vivem na mesma pasta do projeto. Se for importada para Notion/Confluence/GitHub Wiki, atualize os links de acordo com o local de upload de cada arquivo.

---

## Índice

1. [Visão geral do projeto](#1-visão-geral-do-projeto)
2. [Status atual](#2-status-atual)
3. [Mapa de documentos](#3-mapa-de-documentos)
4. [Matriz de rastreabilidade](#4-matriz-de-rastreabilidade)
5. [Glossário técnico](#5-glossário-técnico)
6. [Marco legal em um relance](#6-marco-legal-em-um-relance)
7. [Convenções do projeto](#7-convenções-do-projeto)
8. [Pendências e próximos passos](#8-pendências-e-próximos-passos)
9. [Histórico de versões desta wiki](#9-histórico-de-versões-desta-wiki)

---

## 1. Visão geral do projeto

| | |
|---|---|
| **Desafio** | Desafio 13 — Gestão Inteligente da Frota Municipal |
| **Demandante** | Secretaria Municipal de Administração de Florianópolis |
| **Categoria** | Software / Dados / GovTech |
| **Entregável-chave** | Painel web de frota integrada acoplado a motor de alertas de manutenção preventiva |
| **Critério de sucesso (binário)** | Frota unificada em painel único **+** alerta preventivo disparado antes do vencimento da revisão, em demonstração ao vivo e reproduzível |
| **Diferencial estratégico** | Integração de fontes administrativas (abastecimento, multas, licenciamento) sem depender de hardware de telemetria — ao contrário de soluções comerciais como Cobli e Geotab |

O problema, em uma frase: a frota municipal tem seus dados espalhados em sistemas e planilhas que não conversam entre si, o que empurra a manutenção para o modelo reativo — mais caro e mais arriscado que o preventivo.

---

## 2. Status atual

| Documento | Status | Data | Observação |
|---|---|---|---|
| Briefing técnico (fonte oficial) | 📄 Recebido | — | Documento do demandante; não é editado pela equipe |
| Roadmap de fases | ✅ Concluído | — | Base para todo planejamento subsequente |
| Checkpoint 1 | ✅ Entregue | Prazo 08/07/2026 | Composição da equipe ainda com campos `[preencher]` |
| Arquitetura técnica v1 | 🔁 Substituída pela v2 | 12/07/2026 | Preservada para histórico |
| Arquitetura técnica v2 | ✅ Concluído | 14/07/2026 | Placa canônica dual (Mercosul) + `km_hodometro` no consolidado — ver ADRs 001–002 |
| ADRs 001–003 (`docs/decisoes/`) | ✅ Propostos | 14/07/2026 | Ratificam com o merge do MR da spec 001 em `dev` |
| Quadro Kanban (ClickUp) | ⏳ Pendente | — | CSV de importação pronto; falta subir no ClickUp |
| `gerador_dados.py` | ⏳ Não iniciado | — | Próximo passo técnico nº 1 (ver seção 8) |

---

## 3. Mapa de documentos

### 3.1 Briefing técnico *(fonte oficial — não editar)*
📄 [`Desafio13_briefingFrotaMunicipal.docx`](Desafio13_briefingFrotaMunicipal.docx)

O documento de origem, emitido pela organização da Jornada. Define o problema, o escopo da PoC, os requisitos técnicos, o marco legal e os critérios de avaliação. Todos os outros documentos do projeto derivam dele — em caso de dúvida sobre "o que realmente foi pedido", este é o documento de desempate.

**Estrutura:** 13 seções — introdução (1), o demandante (2), definição do desafio (3), escopo e entregáveis (4: integração de dados, painel web, motor de alertas), requisitos técnicos e arquitetura (5), marco legal (6), dimensão de impacto (7), públicos beneficiários (8), estado da arte / concorrência (9), riscos (10), critérios de avaliação (11), estrutura do desafio (12), considerações finais (13).

### 3.2 Roadmap de fases
📄 [`roadmap_desafio13_frota_municipal.md`](roadmap_desafio13_frota_municipal.md)

Traduz o briefing em um plano de execução faseado. Responde **quando** cada coisa deve ser feita. Seis fases: `Fase 0` (modelagem) → `Fase 1` (integração de dados) → `Fase 2` (motor de alertas) → `Fase 3` (painel web) → `Fase 3a` (painel de custos, tratado como resultado de peso equivalente aos outros dois) → `Fase 4` (demo, conformidade e pitch). Cada fase tem objetivo, entregáveis e "risco a vigiar".

### 3.3 Checkpoint 1 — Entender, planejar e fundamentar
📄 [`checkpoint1_desafio13_frota_municipal.docx`](checkpoint1_desafio13_frota_municipal.docx)

Entregável formal do primeiro marco da Jornada (prazo 08/07/2026). Contém a reformulação do problema, a visão geral da solução, a descrição da PoC realista, a composição da equipe e o checklist do termo de compromisso.

**Pendência conhecida:** a tabela de composição da equipe (seção 4) ainda está com campos `[preencher]` — precisa dos dados reais dos integrantes (nome, papel, habilidades, LinkedIn, Instagram) antes de qualquer reenvio ou uso em outro checkpoint.

### 3.4 Documento técnico de arquitetura
📄 **Vigente:** [`arquitetura_tecnica_desafio13_v2.md`](arquitetura_tecnica_desafio13_v2.md) · v1 preservada em [`arquitetura_tecnica_desafio13_v1.md`](arquitetura_tecnica_desafio13_v1.md) (também em `.docx`)

Responde **como** o roadmap será construído. É o documento mais denso do projeto — 12 seções cobrindo a arquitetura em 4 camadas, as 4 fontes de dados simuladas, o pipeline ETL em 3 estágios, o modelo de dados completo (8 tabelas), a lógica do motor de alertas, o desenho do dashboard, 8 decisões arquiteturais formais (D1–D8, com alternativas consideradas), automação via APScheduler, estrutura do repositório, o resumo de conformidade técnica e o histórico de versões.

**Mudanças da v2 (14–15/07/2026):** placa canônica aceita os dois formatos vigentes (antigo `AAA9999` + Mercosul `AAA9A99`); o `ABASTECIMENTO` consolidado persiste `km_hodometro` (série de km para custo/km por período); a `MANUTENCAO` ganha `categoria` preventiva/corretiva (habilita o comparativo 3–5× do pitch). Racional e pesquisa em [`docs/decisoes/ADR-001`](../docs/decisoes/ADR-001-placa-canonica-dois-formatos.md), [`ADR-002`](../docs/decisoes/ADR-002-persistir-km-hodometro-abastecimento.md) e [`ADR-003`](../docs/decisoes/ADR-003-calibracao-realismo-fontes-simuladas.md).

**Use este documento quando:** precisar decidir stack, entender o esquema do banco, ou justificar uma escolha técnica para a banca.

### 3.5 Quadro Kanban / importação ClickUp
📄 [`clickup_import_desafio13.csv`](clickup_import_desafio13.csv)

Tradução do roadmap em 36 tasks executáveis, agrupadas pelas 6 fases, cada uma com descrição, critério de aceite, papel sugerido (`dados` / `backend` / `frontend` / `docs`) e duas tags transversais: `demo-critico` (participa do disparo do alerta ao vivo — 12 tasks) e `compliance` (LGPD/LAI/Lei 14.133 — não pode ser deixado para última hora).

---

## 4. Matriz de rastreabilidade

Como cada exigência do briefing percorre o roadmap, a arquitetura e o Kanban:

| Resultado esperado (briefing §3) | Fase do roadmap | Seção da arquitetura | Tag no Kanban |
|---|---|---|---|
| Frota unificada em painel único | Fase 3 | §6 Dashboard — visão "Situação da frota" | `demo-critico` |
| Motor de alertas preventivos | Fase 2 | §5 Motor de alertas | `demo-critico` |
| Painel de custos | Fase 3a | §6 Dashboard — visão "Custos" | — |
| Rastreabilidade da origem dos dados (briefing §4.1) | Fase 1 | §3.1 Extract + `fonte_origem` no modelo (§4) | — |
| Tratamento de inconsistências (briefing §5, risco nº 1) | Fase 1 | §3.1 Validate & Transform + `log_qualidade` | `demo-critico` |
| Parametrização de limiares (briefing §4.3) | Fase 0 / Fase 2 | §4 `LIMIAR_CONFIG` | `demo-critico` |
| Conformidade LGPD/LAI (briefing §6, risco de desclassificação) | Fase 4 | §10 Conformidade técnica | `compliance` |
| Rastreabilidade Lei 14.133 (art. 75 §7º) | Fase 4 | §10 Conformidade técnica | `compliance` |
| Viabilidade de implantação (briefing §11) | Fase 4 | §7 D6 — Docker Compose | `demo-critico` |

---

## 5. Glossário técnico

| Termo | Definição | Onde aparece |
|---|---|---|
| **Placa canônica** | Formato normalizado (maiúsculas, sem hífen), aceitando os dois padrões vigentes — antigo `AAA9999` e Mercosul `AAA9A99` (regex `^[A-Z]{3}\d[A-Z\d]\d{2}$`) — usado como chave de reconciliação entre todas as fontes | Arquitetura v2 §2, D7; ADR-001 |
| **`LIMIAR_CONFIG`** | Tabela (não constante no código) que parametriza `tipo_veículo × tipo_manutenção × limite_km × limite_dias` — permite alterar um limiar ao vivo na demo | Roadmap Fase 0/2; Arquitetura §4 |
| **`condutor_pseudo`** | Identificador sintético (`COND-042`) que substitui o nome real do servidor desde a geração dos dados — decisão de conformidade LGPD | Arquitetura §2, §4, D8 |
| **`fonte_origem`** | Campo presente em toda tabela consolidada que registra de qual carga/fonte veio o dado — materializa a auditabilidade exigida pelo briefing | Arquitetura §4, §10 |
| **`log_qualidade`** | Tabela que registra todo dado rejeitado no pipeline com o motivo (`placa_invalida`, `data_ausente`, `duplicado`) — evidência do tratamento de inconsistências | Arquitetura §3.1 |
| **Cenário determinístico** | Veículo A pré-posicionado a ~600 km do limite de km (gatilho ao vivo via CSV) e veículo B com a antecedência de tempo já cruzada (alerta no 1º ciclo do motor), para garantir disparo confiável na demo ao vivo | Roadmap Fase 2; Arquitetura v2 §5.2 |
| **Staging** | Camada intermediária onde os dados brutos são gravados sem transformação, antes da limpeza — garante rastreabilidade | Arquitetura §1, §3.1 |

---

## 6. Marco legal em um relance

| Lei | O que exige | Onde está tratado |
|---|---|---|
| **Lei 14.133/2021** (Licitações) — art. 75, §7º | Rastreabilidade da dispensabilidade de licitação para manutenção de veículos | Arquitetura §10 (`fonte_origem` + `log_qualidade`); Kanban `compliance` |
| **LGPD (Lei 13.709/2018)** | Minimização e pseudonimização de dados vinculados a condutores identificados | Arquitetura §2 (`condutor_pseudo`), D8, §10 |
| **LAI (Lei 12.527/2011)** | Publicação proativa de gastos e contratos em portais de transparência | Arquitetura §6 (toggle Gestor/Pública), §10 |
| **Tensão LGPD × LAI** | Resolver o que é dado agregado exportável vs. dado restrito internamente | Roadmap Fase 4 — **decisão explícita ainda pendente de registro formal** (ver seção 8) |

---

## 7. Convenções do projeto

- **Idioma de trabalho:** português, em todos os documentos e no código de domínio (nomes de tabelas, variáveis de negócio).
- **Formatos de saída:** Markdown (`.md`) para documentos técnicos versionáveis; Word (`.docx`) quando o documento precisa ser editável em formato formal de apresentação.
- **Versionamento:** arquivos-chave seguem o padrão `nome_desafio13_frota_municipal_vN` (ex.: `arquitetura_tecnica_desafio13_v1.md`). Mudança de decisão arquitetural incrementa a versão e registra a alteração no próprio documento.
- **Diagramas:** Mermaid/Graphviz no `.md`; renderizados como imagem ao converter para `.docx`.
- **Divisão de papéis:** `dados` (pipeline, geração de dados), `backend` (motor de alertas, banco, scheduler), `frontend` (dashboard), `docs` (documentação, pitch, conformidade) — espelhada nas tags do Kanban.

---

## 8. Pendências e próximos passos

**Pendências de conteúdo:**
- [ ] Preencher a tabela de composição da equipe no Checkpoint 1 (nomes, papéis, LinkedIn, Instagram)
- [ ] Registrar formalmente a decisão da tensão LGPD × LAI (o quê é agregado exportável vs. restrito) — hoje descrita como diretriz no roadmap, mas ainda sem decisão documentada como as demais (D1–D8)
- [ ] Subir as 36 tasks do `clickup_import_desafio13.csv` no quadro Kanban

**Próximos passos técnicos** (ordem sugerida pela arquitetura §11):
1. `gerador_dados.py` — os 4 datasets simulados com inconsistências propositais
2. Extratores + transformação com `log_qualidade` funcionando
3. Motor de alertas + cenário determinístico com os 2 veículos "no gatilho"
4. Dashboard nas 3 visões + toggle público
5. Ensaio do roteiro de demo com o ciclo agendado em 1–2 min

---

## 9. Histórico de versões desta wiki

| Versão | Data | Mudança |
|---|---|---|
| v1.1 | 14/07/2026 | Arquitetura v2 registrada (placa dual + `km_hodometro`); ADRs 001–003 adicionados ao status; glossário de placa canônica atualizado |
| v1 | 13/07/2026 | Criação inicial — índice, mapa de documentos, matriz de rastreabilidade, glossário e marco legal |

*Convenção: ao adicionar um novo documento ao projeto (ex.: `gerador_dados.py`, documentação da API fake, ADRs futuros), atualize a seção 3 com uma nova entrada e a seção 4 se houver rastreabilidade nova a registrar.*
