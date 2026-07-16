# Quadro de Tasks — Desafio 13: Gestão Inteligente da Frota Municipal

**Fonte:** `clickup_import_desafio13.csv` · **Total de tasks:** 36 · **Status inicial:** todas em `to do`

Este documento é a versão legível em Markdown do CSV de importação do quadro Kanban. Serve para revisão e discussão com a equipe antes (ou em vez) de subir ao ClickUp — o CSV continua sendo o arquivo de importação oficial.

**Legenda:** 🔴 `demo-critico` = participa do disparo do alerta ao vivo · 🟡 `compliance` = LGPD/LAI/Lei 14.133, não pode ficar para a última hora.

---

## Índice

- [Fase 0 — Modelagem](#fase-0-modelagem) (5 tasks)
- [Fase 1 — Integração de dados](#fase-1-integração-de-dados) (10 tasks)
- [Fase 2 — Motor de alertas](#fase-2-motor-de-alertas) (6 tasks)
- [Fase 3 — Painel da frota](#fase-3-painel-da-frota) (6 tasks)
- [Fase 3a — Painel de custos](#fase-3a-painel-de-custos) (3 tasks)
- [Fase 4 — Demo e conformidade](#fase-4-demo-e-conformidade) (6 tasks)
- [Resumo por papel e prioridade](#resumo-por-papel-e-prioridade)

---

## Fase 0 — Modelagem

| # | Task | Descrição / Critério de aceite | Papel | Prioridade |
|---|---|---|---|---|
| 1 | Definir papéis da equipe | Cada integrante com papel claro: dados, backend, frontend, docs/pitch. Critério: tabela de papéis registrada no repositório. | 👥 Todos | Normal |
| 2 | Decidir dados reais vs simulados | Confirmar com a organização se haverá amostra real; caso contrário, formalizar uso de dados simulados com estrutura representativa. | 🗂️ Dados | Normal |
| 3 | Validar modelo de dados unificado | Revisar o ERD do documento de arquitetura v2 (8 tabelas, placa como chave canônica nos formatos AAA9999/AAA9A99 — ADR-001; ABASTECIMENTO com km_hodometro — ADR-002). Critério: equipe aprova ou registra ajustes. | 🗂️ Dados | Normal |
| 4 | Definir limiares iniciais (LIMIAR_CONFIG) 🔴 demo-crítico | Preencher a tabela para ≥2 tipos de veículo × 2-3 tipos de manutenção, com limite_km, limite_dias e antecedências. | ⚙️ Backend | **Alta** |
| 5 | Mapear campos com dado pessoal 🟡 compliance | Marcar no modelo os campos que vinculam servidor identificado (condutor, CNH, matrícula). Critério: lista registrada em docs/. | 📄 Docs | **Alta** |

## Fase 1 — Integração de dados

| # | Task | Descrição / Critério de aceite | Papel | Prioridade |
|---|---|---|---|---|
| 1 | Criar gerador_dados.py (4 fontes) 🔴 demo-crítico | Gerar CSV de abastecimento, JSON de multas, XLSX de manutenção e SQLite de licenciamento com inconsistências propositais documentadas. | 🗂️ Dados | **Alta** |
| 2 | Subir API fake de multas (FastAPI) | Endpoint JSON servindo as multas simuladas, com CNH pseudonimizada. Critério: GET retorna dados válidos. | ⚙️ Backend | Normal |
| 3 | Modelar banco (SQLAlchemy + migrations) | Tabelas staging, consolidadas, LIMIAR_CONFIG, ALERTA e log_qualidade criadas via models.py. | ⚙️ Backend | Normal |
| 4 | Extrator de abastecimento (CSV/pasta monitorada) 🔴 demo-crítico | Lê CSVs da pasta inbox e grava bruto no staging com carimbo de carga e fonte_origem. | 🗂️ Dados | **Alta** |
| 5 | Extrator de multas (API) | Consome o endpoint FastAPI e grava no staging. | 🗂️ Dados | Normal |
| 6 | Extrator de manutenção (XLSX) | Lê planilha multi-abas e grava no staging. | 🗂️ Dados | Normal |
| 7 | Extrator de licenciamento (SQLite) | Consulta o banco legado simulado e grava no staging. | 🗂️ Dados | Normal |
| 8 | Transformação e regras de qualidade 🔴 demo-crítico | Normalização de placa, parsing tolerante de datas, decimais, vocabulário e deduplicação. Critério: registros inválidos vão para log_qualidade com motivo. | 🗂️ Dados | **Alta** |
| 9 | Carga idempotente (upsert) 🔴 demo-crítico | Rodar o pipeline 2x sobre os mesmos dados não duplica registros. Critério: teste comprovando. | ⚙️ Backend | **Alta** |
| 10 | Documentar pipeline e rastreabilidade | Regras de qualidade e origem de cada dado documentadas em docs/ (exigência briefing 4.1). | 📄 Docs | Normal |

## Fase 2 — Motor de alertas

| # | Task | Descrição / Critério de aceite | Papel | Prioridade |
|---|---|---|---|---|
| 1 | Alerta por quilometragem 🔴 demo-crítico | Dispara quando km_desde_ultima >= limite_km - antecedencia_km. Critério: teste unitário passando. | ⚙️ Backend | **Alta** |
| 2 | Alerta por tempo 🔴 demo-crítico | Dispara quando dias_desde_ultima >= limite_dias - antecedencia_dias. Critério: teste unitário passando. | ⚙️ Backend | **Alta** |
| 3 | Idempotência e histórico de alertas | Sem duplicar alerta ativo para mesma (placa, tipo, gatilho); alertas resolvidos preservados como histórico. | ⚙️ Backend | Normal |
| 4 | Alerta dados_insuficientes | Veículo sem manutenção registrada ou km não confiável gera alerta especial em vez de ser ignorado. | ⚙️ Backend | Normal |
| 5 | Cenário determinístico da demo 🔴 demo-crítico | Veículo A a ~600 km do limite de km (gatilho ao vivo via CSV) e veículo B com antecedência de tempo já cruzada (166 dias — alerta no 1º ciclo); dados gerados com data-âncora explícita. Critério: alerta dispara de forma reproduzível. | 🗂️ Dados | **Alta** |
| 6 | Agendamento (APScheduler) 🔴 demo-crítico | ETL + motor rodando em ciclo configurável por variável de ambiente (1-2 min na demo). | ⚙️ Backend | **Alta** |

## Fase 3 — Painel da frota

| # | Task | Descrição / Critério de aceite | Papel | Prioridade |
|---|---|---|---|---|
| 1 | Visão situação da frota 🔴 demo-crítico | Lista com semáforo ok/atenção/vencido ordenada por urgência; responde 'o que vence esta semana' sem cliques. | 🖥️ Frontend | **Alta** |
| 2 | Drill-down por veículo | Histórico de abastecimentos, manutenções, multas e licenciamento por placa. | 🖥️ Frontend | Normal |
| 3 | Visão de alertas 🔴 demo-crítico | Alertas ativos em destaque + histórico, com gatilho (km/tempo) e limiar exibidos. | 🖥️ Frontend | **Alta** |
| 4 | Toggle Gestor/Pública 🟡 compliance | Visão pública oculta condutor_pseudo e exibe apenas agregados — materializa LGPD × LAI. | 🖥️ Frontend | **Alta** |
| 5 | Auto-refresh do painel 🔴 demo-crítico | Painel atualiza sozinho (~30s) para o alerta 'aparecer ao vivo' na demo. | 🖥️ Frontend | **Alta** |
| 6 | Teste de usabilidade externo | 1-2 pessoas fora do time navegam simulando gestor público; ajustes registrados. | 📄 Docs | Normal |

## Fase 3a — Painel de custos

| # | Task | Descrição / Critério de aceite | Papel | Prioridade |
|---|---|---|---|---|
| 1 | Consolidação de gastos | Gastos por veículo, período e tipo de despesa (combustível, manutenção, multas). | 🖥️ Frontend | Normal |
| 2 | Comparativo entre veículos | Pelo menos uma comparação destacando custo desproporcional (candidato a renovação). | 🖥️ Frontend | Normal |
| 3 | Marcar indicadores derivados vs calculados | Cada indicador informa se vem direto das fontes ou é calculado pela plataforma. | 📄 Docs | Normal |

## Fase 4 — Demo e conformidade

| # | Task | Descrição / Critério de aceite | Papel | Prioridade |
|---|---|---|---|---|
| 1 | Análise de impacto econômico | Estimativa quantificada com benchmarks (corretiva 3-5x mais cara; redução 20-30%) aplicados à frota simulada. | 📄 Docs | Normal |
| 2 | Documento de conformidade LGPD/LAI/14.133 🟡 compliance | Base legal por campo, pseudonimização, tensão LGPD×LAI resolvida, retenção e art. 75 §7º referenciado. | 📄 Docs | **Alta** |
| 3 | Docker Compose funcional 🔴 demo-crítico | docker compose up sobe banco + app do zero em máquina limpa. | ⚙️ Backend | **Alta** |
| 4 | Ensaio da demo ao vivo 🔴 demo-crítico | Roteiro completo ensaiado ≥3x com o ciclo agendado; tempo cronometrado. | 👥 Todos | **Alta** |
| 5 | Vídeo plano B do disparo do alerta 🔴 demo-crítico | Gravação do roteiro completo caso algo falhe ao vivo. | 📄 Docs | **Alta** |
| 6 | Pitch e posicionamento | Discurso frente ao mercado: fontes administrativas sem hardware, baixo custo, aderência ao setor público. | 📄 Docs | Normal |

---

## Resumo por papel e prioridade

| Papel | Nº de tasks |
|---|---|
| ⚙️ Backend | 10 |
| 🗂️ Dados | 9 |
| 📄 Docs | 8 |
| 🖥️ Frontend | 7 |
| 👥 Todos | 2 |

**Prioridade alta:** 18 tasks (todas com tag `demo-critico` e/ou `compliance`) · **Prioridade normal:** 18 tasks

**Tasks demo-críticas:** 15 — formam o caminho mínimo até o disparo do alerta ao vivo; se atrasarem, ameaçam o critério de sucesso binário do briefing.

**Tasks de compliance:** 3 — LGPD/LAI/Lei 14.133; o briefing trata a ausência de estratégia de proteção de dados como possível critério de desclassificação.

---

*Convenção: ao importar no ClickUp, cada linha das tabelas acima vira uma task; o nome do épico (fase) deve ser criado como Lista ou Epic-tag correspondente. Status inicial de todas as tasks: `to do`.*