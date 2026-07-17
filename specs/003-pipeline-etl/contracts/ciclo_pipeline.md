# Contrato — Ciclo do Pipeline ETL (Spec 003)

**Branch**: `feature/003-pipeline-etl` | **Date**: 2026-07-17

Contrato do ponto de entrada único do pipeline (FR-008), consumido pelo agendador/motor
(spec 004), pelo empacotamento (spec 007) e pelos testes. As tabelas que o pipeline escreve
são regidas pelo contrato da spec 002 (`contracts/esquema_tabelas.md`) — este documento fixa
**como invocar o ciclo e o que ele garante**.

## Invocação

```bash
python -m pipeline.run_etl        # executa exatamente 1 ciclo completo (E→T→L, 4 fontes + cadastro)
```

```python
from pipeline.run_etl import executar_ciclo
resumo = executar_ciclo()         # mesma semântica, importável (é assim que o APScheduler da spec 004 agenda)
```

| Garantia | Detalhe |
|---|---|
| Idempotente | N execuções sobre as mesmas fontes → mesmo estado em consolidadas **e** `log_qualidade` (SC-001; research R1/R2/R3) |
| Isolamento por fonte | Falha de uma fonte é registrada (`fonte_indisponivel` em `log_qualidade`) e as demais processam normalmente (SC-005; R8) |
| Duração | < 1 min no volume da PoC (SC-004) — compatível com ciclo de 1–2 min |
| Código de saída (CLI) | `0` mesmo com fonte indisponível (falha registrada é operação normal); `≠ 0` apenas em erro estrutural (banco inacessível, esquema ausente) |
| Pré-requisito | Esquema criado (`python -m db.init_db`, contrato 002). O pipeline NÃO cria/migra esquema |
| Acesso a banco | Exclusivamente via `db.config.get_engine()`/`get_session()` (contrato 002) |
| Concorrência | Um ciclo por vez (agendador não sobrepõe execuções — responsabilidade da spec 004; o upsert torna sobreposição acidental inócua, não recomendada) |

## Retorno de `executar_ciclo()` — resumo do ciclo

Dicionário por fonte (`cadastro`, `abastecimento`, `multas`, `manutencao`, `licenciamento`):

| Campo | Significado |
|---|---|
| `situacao` | `ok` \| `sem_novidade` (hash já visto — R1) \| `indisponivel` (R8) |
| `extraidos` | linhas brutas gravadas no staging neste ciclo |
| `consolidados` | linhas que chegaram às consolidadas (inserts + updates efetivos) |
| `rejeitados` | linhas enviadas a `log_qualidade` neste ciclo |

O resumo é para diagnóstico/log do agendador — painéis (005/006) leem **apenas o banco**
(constitution VI), nunca este retorno.

## Configuração (env vars — constitution V)

Defaults apontam para o layout do repositório; tudo sobrescrevível sem tocar em código
(`.env.example` atualizado neste MR):

| Variável | Default | Uso |
|---|---|---|
| `DATABASE_URL` | `sqlite:///db/frota.db` | herdada do contrato 002 (via `db.config`) |
| `PIPELINE_INBOX` | `data/inbox` | pasta monitorada de CSVs de abastecimento |
| `MULTAS_API_URL` | `http://localhost:8000` | base da API de multas (compose: `http://fake_api:8000`) |
| `PIPELINE_XLSX_MANUTENCAO` | `data/seeds/manutencao.xlsx` | planilha de manutenção |
| `PIPELINE_SQLITE_LICENCIAMENTO` | `data/seeds/licenciamento.sqlite` | base legada de licenciamento |
| `PIPELINE_CADASTRO_VEICULOS` | `data/seeds/veiculos.json` | cadastro canônico da frota (R4) |

O **intervalo do ciclo** não é deste contrato: pertence ao agendador (spec 004).

## O que o ciclo escreve (resumo; detalhes no data-model.md)

| Alvo | Operação | Chave / Regra |
|---|---|---|
| `stg_*` | append por lote (`carga_em` único por fonte/ciclo) | só quando o conteúdo da fonte é novo (hash — R1) |
| `veiculo` | upsert por `placa` (cadastro R4) + atualização de `km_atual` (R10) | `km_atual` nunca diminui |
| `abastecimento` | insert `on_conflict_do_nothing` | `(placa, data, km_hodometro)`; km NULL não colide (ADR-004 caminho 2) |
| `manutencao` | insert `on_conflict_do_nothing` | `(placa, data, tipo)` |
| `multa` | insert `on_conflict_do_nothing` (sem alvo) | `ux_multa_upsert` com coalesce (ADR-004); `cnh`/`gravidade`/`codigo_infracao` **nunca** chegam à consolidada (FR-011) |
| `licenciamento` | upsert `do_update` por `placa` | vencimento mais recente vence (dedup R3) |
| `log_qualidade` | append | 1 linha por rejeição/falha, motivo do vocabulário abaixo |

## `fonte_origem` — formato (rastreabilidade, SC-003)

`<identificador>@sha256:<12 primeiros hex do conteúdo>`

| Fonte | Identificador |
|---|---|
| Abastecimento | caminho relativo do CSV (ex.: `data/inbox/gatilho_demo_abastecimento.csv`) |
| Multas | URL efetiva (ex.: `http://localhost:8000/multas`) |
| Manutenção | caminho do XLSX; a aba vai em `stg_manutencao.aba_origem` |
| Licenciamento | caminho do .sqlite |
| Cadastro | caminho do veiculos.json |

## Motivos de rejeição (vocabulário fechado — research R7)

`placa_invalida` · `data_ausente` · `data_invalida` · `valor_invalido` ·
`tipo_desconhecido` · `categoria_desconhecida` · `situacao_desconhecida` · `duplicado` ·
`veiculo_desconhecido` · `fonte_indisponivel`

Semântica de `duplicado`: **intra-lote** (2ª ocorrência da chave natural na mesma carga).
Registro já consolidado que reaparece em ciclo posterior é idempotência (no-op, sem log).

## Estabilidade do contrato

Mudança em invocação, retorno, env var, formato de `fonte_origem` ou vocabulário de motivos
= atualização deste arquivo no MESMO MR + aviso às specs consumidoras (004: invocação e
retorno; 005/006: motivos e `fonte_origem` exibidos; 007: env vars do compose). As regras de
qualidade em si são documentadas em `pipeline/README.md` (FR-009) e no `data-model.md`.
