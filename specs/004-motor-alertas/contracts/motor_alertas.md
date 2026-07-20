# Contrato — Motor de Alertas e Ciclo Agendado (Spec 004)

**Branch**: `feature/004-motor-alertas` | **Date**: 2026-07-20

Contrato dos pontos de entrada do motor e do agendador, consumidos pelos painéis (005/006, que
leem os `alerta` resultantes), pelo empacotamento (spec 007, que sobe o `scheduler.py`) e pelos
testes. As tabelas lidas/escritas são regidas pelo contrato da spec 002
(`specs/002-modelo-dados-banco/contracts/esquema_tabelas.md`, § Spec 004). O ciclo do ETL é regido
pelo contrato da spec 003 (`specs/003-pipeline-etl/contracts/ciclo_pipeline.md`). Este documento
fixa **como invocar o motor/ciclo e o que garantem**.

## Invocação — motor isolado

```bash
python -m alertas.motor          # executa 1 verificação sobre o estado consolidado atual
```

```python
from alertas.motor import verificar_alertas
resumo = verificar_alertas()               # hoje = date.today()
resumo = verificar_alertas(hoje=algum_date)  # relógio injetável (testes/determinismo)
```

| Garantia | Detalhe |
|---|---|
| Idempotente | N verificações sobre o mesmo estado → **zero** alertas ativos duplicados (SC-002); colisão no índice `ux_alerta_ativo` é no-op |
| Sem cache | Lê `limiar_config` **a cada** verificação; edição ao vivo vale na próxima verificação (SC-004/FR-002) |
| Create-only | Nunca faz DELETE/UPDATE em `alerta`; resolução é ação externa (painel/script) |
| Só o banco | Lê `veiculo`/`manutencao`/`limiar_config`/`abastecimento`; escreve `alerta`. Nunca lê staging nem arquivo-fonte (FR-007) |
| Acesso a banco | Exclusivamente via `db.config.get_engine()`/`get_session()` (contrato 002) |
| Dois dialetos | Comportamento idêntico em SQLite e PostgreSQL 16 (learning lesson "dois bancos-alvo") |
| Pré-requisito | Esquema criado (`python -m db.init_db`, contrato 002). O motor NÃO cria/migra esquema |
| Código de saída (CLI) | `0` em execução normal (inclusive 0 alertas criados); `≠0` só em erro estrutural (banco inacessível, esquema ausente) |

### Retorno de `verificar_alertas()` — resumo da verificação

Dicionário de diagnóstico (log do agendador). **Painéis leem apenas o banco (constitution VI),
nunca este retorno.**

| Campo | Significado |
|---|---|
| `veiculos_avaliados` | veículos percorridos na verificação |
| `criados_km` | novos alertas `km` inseridos neste ciclo |
| `criados_tempo` | novos alertas `tempo` inseridos neste ciclo |
| `criados_dados_insuficientes` | novos alertas `dados_insuficientes` inseridos neste ciclo |
| `ja_ativos` | candidatos que colidiram com alerta ativo existente (no-op idempotente) |

Contagens derivam de inserts efetivos (delta de `COUNT`/savepoint bem-sucedido), **não** de
`rowcount` — evita o `-1` do psycopg (learning lesson, Bug 2).

## Invocação — ciclo agendado (ETL + motor)

```bash
python scheduler.py              # sobe o APScheduler; roda até Ctrl-C / SIGTERM
```

| Garantia | Detalhe |
|---|---|
| Ordem | Cada tick executa **`executar_ciclo()` (spec 003) → `verificar_alertas()`** nessa ordem (arquitetura §8); a verificação vê o estado após a carga do mesmo ciclo |
| Não-sobreposição | `max_instances=1` + `coalesce=True`: um ciclo por vez; ticks perdidos por ciclo longo são coalescidos, não empilhados |
| Resiliência | Falha isolada de fonte no ETL (SC-005 spec 003) não impede a verificação; erro estrutural num tick é logado e o scheduler segue para o próximo tick |
| Intervalo | `IntervalTrigger(seconds=CICLO_INTERVALO_SEGUNDOS)`; alterar o intervalo = **zero** código (SC-005) |

## Configuração (env vars — constitution V)

| Variável | Default | Uso |
|---|---|---|
| `CICLO_INTERVALO_SEGUNDOS` | `90` | intervalo do agendador (demo 1–2 min); lido por `alertas.config.intervalo_ciclo_segundos()` |
| `DATABASE_URL` | `sqlite:///db/frota.db` | herdada do contrato 002 (via `db.config`) |

> As env vars das fontes do ETL (`PIPELINE_*`, `MULTAS_API_URL`) são do contrato da spec 003 e
> continuam valendo quando o scheduler roda o ciclo completo. `.env.example` ganha
> `CICLO_INTERVALO_SEGUNDOS` neste MR.

## Regras de disparo (referência — detalhe em data-model.md §3)

Para cada veículo × tipo de manutenção **avaliável** (par com linha em `limiar_config` para o
`tipo_veiculo`), lendo o limiar a cada verificação:

| Gatilho | Condição | `limiar_id` | `detalhe` |
|---|---|---|---|
| `km` | `km_atual − km_no_momento ≥ limite_km − antecedencia_km` (km confiável — R5) | id do limiar | opcional (contexto) |
| `tempo` | `hoje − data_última ≥ limite_dias − antecedencia_dias` | id do limiar | opcional (contexto) |
| `dados_insuficientes` | veículo com ≥1 impedimento (sem manutenção do tipo, km não confiável, ou sem limiar para o `tipo_veiculo`) | **NULL** | **obrigatório** — enumera as causas |

`dados_insuficientes` é **um por veículo** (o índice colapsa `limiar_id` NULL em sentinela `-1`);
o `detalhe` agrega todas as causas (R6). Par **sem linha** em `limiar_config` não é impedimento por
si — só conta quando o veículo não tem **nenhum** tipo avaliável.

## Vocabulários (fechados)

- `tipo_gatilho` ∈ `{km, tempo, dados_insuficientes}` (CHECK no banco).
- `situacao` ∈ `{ativo, resolvido}` (CHECK no banco); motor só cria `ativo`.

## Estabilidade do contrato

Mudança em invocação, assinatura de `verificar_alertas`, chaves do retorno, env var ou regra de
disparo = atualização deste arquivo **no mesmo MR** + aviso às specs consumidoras (005/006 leem os
`alerta` gerados; 007 sobe o `scheduler.py` e as env vars no compose). Mudança em coluna/constraint
de `alerta`/`limiar_config` exige migration + atualização do contrato da spec 002 (esquema é dela).
