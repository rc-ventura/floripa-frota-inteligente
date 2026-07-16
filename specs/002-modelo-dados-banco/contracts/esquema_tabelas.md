# Contrato — Esquema do Banco Consolidado (Spec 002)

**Branch**: `feature/002-modelo-dados-banco` | **Date**: 2026-07-16

Este é o contrato de dados entre as camadas: pipeline (003), motor (004) e painéis (005/006)
conversam **exclusivamente** por estas tabelas (constitution VI). Detalhes de colunas/tipos em
`data-model.md` — este contrato fixa o que cada consumidor pode assumir.

## Contrato de inicialização (comando único — FR-007)

```bash
python -m db.init_db        # alembic upgrade head + seed da LIMIAR_CONFIG (idempotente)
```

| Garantia | Detalhe |
|---|---|
| Idempotente | Rodar N vezes → mesmo estado, sem erro nem perda de dados (SC-004) |
| Ambiente | `DATABASE_URL` (env var); default `sqlite:///db/frota.db`; demo usa PostgreSQL 16 — mesmo comando, mesmo esquema (SC-001) |
| Seed | `limiar_config` semeada de `data/seeds/limiares_semente.json` (fonte única); upsert por `(tipo_veiculo, tipo_manutencao)` que NÃO sobrescreve valores existentes (edições ao vivo sobrevivem a re-init). Recalibração deliberada: `python -m db.seed_limiares --sobrescrever` adota os valores do JSON num banco existente |
| Acesso | Componentes obtêm engine/sessão via `db.config.get_engine()` / `get_session()` — nunca criam URL própria |

## O que cada spec pode assumir

### Spec 003 — Pipeline (escreve staging + consolidadas + log)

| Operação | Contrato |
|---|---|
| Extract → staging | `stg_*` aceita QUALQUER texto (tudo TEXT nullable); obrigatórios apenas `carga_em` e `fonte_origem` (arquivo/endpoint). `stg_manutencao.aba_origem` recebe o nome da aba do XLSX |
| Load → consolidadas (upsert) | Chaves de upsert garantidas por UNIQUE no banco: `manutencao (placa, data, tipo)` · `abastecimento (placa, data, km_hodometro)` · `multa (placa, data, valor, condutor_pseudo)` · `licenciamento (placa)` · `veiculo (placa)`. Limitação aceita da PoC: duas multas legítimas idênticas no mesmo dia colidem na chave — a 2ª vai para `log_qualidade` com motivo `duplicado` (comportamento esperado, não erro) |
| Normalização de placa | Constante exportada `db.models.REGEX_PLACA_CANONICA` (`^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$` — ADR-001); modelo rejeita placa fora do canônico (`ValueError` via `@validates`) |
| Vocabulários (CHECK no banco) | `manutencao.tipo` ∈ {troca_oleo, filtros, pneus, revisao_geral} · `manutencao.categoria` ∈ {preventiva, corretiva} · `multa.situacao` ∈ {pendente, paga} · `licenciamento.situacao` ∈ {em_dia, vencido} |
| Minimização LGPD | `multa` consolidada NÃO tem colunas `cnh`/`gravidade`/`codigo_infracao` — o descarte (spec 003 FR-011) é estrutural, não opcional |
| Rejeições | `log_qualidade (fonte, registro_bruto, motivo_rejeicao, carga_em)` — todos NOT NULL; motivos em snake_case |
| km do veículo | Pipeline atualiza `veiculo.km_atual` com a maior leitura válida E persiste a leitura em `abastecimento.km_hodometro` (ADR-002) |

### Spec 004 — Motor (lê consolidadas + config; escreve alertas)

| Operação | Contrato |
|---|---|
| Limiar | Ler `limiar_config` **a cada verificação** (sem cache de processo — SC-002); par (tipo_veiculo, tipo_manutencao) ausente = não-avaliável, nunca default |
| Última manutenção | Índice `ix_manutencao_placa_tipo_data` suporta a consulta "última por (placa, tipo)" |
| Inserir alerta | `tipo_gatilho` ∈ {km, tempo, dados_insuficientes}; `limiar_id` obrigatório para km/tempo, NULL para dados_insuficientes (com `detalhe` preenchido); o índice único parcial `ux_alerta_ativo` faz o banco rejeitar duplicata de alerta ativo — o motor trata o conflito como no-op |
| Histórico | Proibido DELETE em `alerta`; resolução = UPDATE `situacao='resolvido'`; recorrência = nova linha `ativo` |

### Specs 005/006 — Painéis (somente leitura)

| Visão | Contrato |
|---|---|
| Semáforo/urgência | `licenciamento.vencimento` (indexado) + `alerta.situacao` (indexado) |
| Drill-down | 4 históricos por `placa` (índices `(placa, data)` em abastecimento/multa; `(placa, tipo, data)` em manutenção) |
| Custos | `abastecimento.valor`, `manutencao.valor` + `categoria` (comparativo corretiva×preventiva 3–5×), `multa.valor`; custo/km por período = max−min de `abastecimento.km_hodometro` no período |
| Visão pública (LGPD) | `condutor_pseudo` é o ÚNICO campo de condutor existente; agregados nunca o expõem |
| Proveniência | `fonte_origem` presente em toda consolidada para o tooltip "derivado da fonte X" |

## Estabilidade do contrato

Mudança em tabela/coluna/constraint deste contrato = nova migration Alembic + atualização
deste arquivo no MESMO MR + aviso às specs consumidoras. O diagrama de referência é o ERD da
arquitetura v2 §4; divergências deliberadas estão registradas (research R6–R8: `detalhe` e
`limiar_id` NULL em alerta; `fonte_origem` em veiculo; chaves de upsert).
