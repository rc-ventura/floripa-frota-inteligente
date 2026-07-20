# Pipeline ETL — Integração das 4 fontes (spec 003)

Documentação das **regras de qualidade** e da **rastreabilidade da origem** de cada dado
(exigência do briefing 4.1 — FR-009; task 10 da Fase 1 do kanban). O contrato de invocação
está em `specs/003-pipeline-etl/contracts/ciclo_pipeline.md`; o mapeamento coluna a coluna,
em `specs/003-pipeline-etl/data-model.md`.

O pipeline roda em três estágios — **Extract → Validate & Transform → Load** (arquitetura
§3) — integrando as 4 fontes legadas heterogêneas no banco consolidado da spec 002. Conversa
com o mundo **só pelo banco** (constitution VI): lê arquivos/endpoint das fontes e escreve
`stg_*` (bruto), consolidadas (upsert) e `log_qualidade` (rejeições) — nada mais.

## Como rodar um ciclo

```bash
uv run python -m db.init_db            # pré-requisito: esquema criado (spec 002)
cp data/seeds/abastecimento.csv data/inbox/      # deposita a Fonte 1 na pasta monitorada
uv run uvicorn fake_api.main:app --port 8000 &   # Fonte 2 (multas) no ar
uv run python -m pipeline.run_etl      # executa 1 ciclo completo (E→T→L das 4 fontes)
```

Ou, importável (é assim que o agendador da spec 004 o aciona, sem subprocess):

```python
from pipeline.run_etl import executar_ciclo
resumo = executar_ciclo()   # {fonte: {situacao, extraidos, consolidados, rejeitados}}
```

Fontes 3 (XLSX) e 4 (SQLite) usam os arquivos de `data/seeds/` por default — nada a preparar.
Caminhos e URLs são parametrizáveis por variável de ambiente (`.env.example`): `PIPELINE_INBOX`,
`MULTAS_API_URL`, `PIPELINE_XLSX_MANUTENCAO`, `PIPELINE_SQLITE_LICENCIAMENTO`,
`PIPELINE_CADASTRO_VEICULOS`, `DATABASE_URL`.

## Rastreabilidade da origem (constitution II)

Todo registro carrega de onde veio e de qual carga:

- **Staging** (`stg_*`): `carga_em` (carimbo de data/hora do lote) + `fonte_origem`.
- **Consolidadas**: `fonte_origem`, copiado do registro de staging que originou o dado.
- **`fonte_origem`** tem o formato `<identificador>@sha256:<12 primeiros hex do conteúdo>`:

  | Fonte | Identificador | Exemplo |
  |---|---|---|
  | Abastecimento | caminho do CSV | `data/inbox/abastecimento.csv@sha256:3fa9c01b22de` |
  | Multas | URL do endpoint | `http://localhost:8000/multas@sha256:9c1d44aa07b1` |
  | Manutenção | caminho do XLSX (aba em `stg_manutencao.aba_origem`) | `data/seeds/manutencao.xlsx@sha256:…` |
  | Licenciamento | caminho do `.sqlite` | `data/seeds/licenciamento.sqlite@sha256:…` |
  | Cadastro | caminho do `veiculos.json` | `data/seeds/veiculos.json@sha256:…` |

O hash do conteúdo é também o mecanismo de **detecção de novidade** (research R1): fonte cujo
conteúdo já foi visto é pulada no ciclo (`situacao=sem_novidade`) — reprocessar o mesmo arquivo,
ou um renomeado com conteúdo idêntico, não duplica nada e não infla o `log_qualidade`.

## Regras de qualidade por fonte

Cada célula normalizável **converge para o canônico**; o que não dá vai para `log_qualidade`
com um motivo — **nunca é descartado em silêncio** (constitution II/III). A ordem de precedência
de rejeição num registro é fixa: placa → cadastro → data → campos numéricos/vocabulários → dedup.

### Fonte 1 — Abastecimento (CSV na pasta monitorada) → `abastecimento`

| Campo | Regra | Rejeição possível |
|---|---|---|
| `placa` | canônica ADR-001 (upper, sem hífen/espaço; `RLL-8062` → `RLL8062`) + existe no cadastro | `placa_invalida`, `veiculo_desconhecido` |
| `data` | `dd/mm/aaaa` ou `aaaa-mm-dd` | `data_ausente`, `data_invalida` |
| `litros`, `valor` | vírgula decimal → número (`31,5` → `31.5`) | `valor_invalido` |
| `km` | inteiro; **ausente é válido** (nullable — ADR-002) | `valor_invalido` (se presente e não numérico) |

Chave de dedup intra-lote: `(placa, data, km_hodometro)` — `km` NULL **não** colide (ADR-004
caminho 2: dois abastecimentos sem km no mesmo dia podem ser eventos reais). Após a carga,
`veiculo.km_atual` recebe `MAX(km_hodometro)` da placa **se superar** o valor atual — nunca
regride (R10/FR-010).

### Fonte 2 — Multas (API JSON) → `multa`

| Campo | Regra | Rejeição possível |
|---|---|---|
| `placa` | canônica (minúsculas na fonte: `oll2058` → `OLL2058`) + cadastro | `placa_invalida`, `veiculo_desconhecido` |
| `data` | `aaaa-mm-dd` | `data_ausente`, `data_invalida` |
| `valor` | número (NOT NULL na consolidada) | `valor_invalido` |
| `situacao` | ∈ {`pendente`, `paga`} | `situacao_desconhecida` |
| `cnh`, `gravidade`, `codigo_infracao` | **descartados na carga** — a consolidada nem tem as colunas (FR-011, minimização LGPD) | — |

Chave de dedup: `(placa, data, valor, coalesce(condutor_pseudo, ''))` — espelha o índice
`ux_multa_upsert` (ADR-004): duas multas idênticas sem condutor **colidem** (o coalesce faz
NULL colidir), e a 2ª vai a `log_qualidade` como `duplicado`.

> **LGPD**: a `cnh` sintética é retida no `stg_multas` como trilha bruta de auditoria (expurgo
> via `carga_em`), mas **nenhum valor dela chega a qualquer consolidada** — o descarte é
> estrutural, não opcional.

### Fonte 3 — Manutenção (XLSX, 3 abas) → `manutencao`

| Campo | Regra | Rejeição possível |
|---|---|---|
| `placa` | canônica + cadastro | `placa_invalida`, `veiculo_desconhecido` |
| `data` | `aaaa-mm-dd` (TEXT) **ou** serial Excel (inteiro, ex.: `46068`) | `data_ausente`, `data_invalida` |
| `tipo` | vocabulário → {`troca_oleo`, `filtros`, `pneus`, `revisao_geral`} — por radical, sem acento (`Troca Óleo`, `REVISAO 10000`, `Revisão 10.000 km` → canônicos) | `tipo_desconhecido` |
| `categoria` | → {`preventiva`, `corretiva`} (`prev.`, `CORRETIVA` → canônicas) | `categoria_desconhecida` |
| `km_no_momento`, `valor` | inteiro/número; ausente é válido (nullable) | `valor_invalido` (se presente e inválido) |

Chave de dedup: `(placa, data, tipo)`.

### Fonte 4 — Licenciamento (SQLite legado, somente leitura) → `licenciamento`

| Campo | Regra | Rejeição possível |
|---|---|---|
| `placa` | canônica + cadastro; **linhas duplicadas** por design na fonte | `placa_invalida`, `veiculo_desconhecido`, `duplicado` |
| `vencimento` | 3 formatos (dd/mm/aaaa, ISO, serial); ausente é válido | `data_invalida` |
| `situacao` | ∈ {`em_dia`, `vencido`} | `situacao_desconhecida` |

Dedup por `placa` mantendo o **vencimento mais recente**; a linha preterida vai a
`log_qualidade` como `duplicado`. Carga por `on_conflict_do_update` (a placa é 1:1 com veículo).

### Cadastro — `veiculos.json` (referência interna, **não** é fonte legada)

Carregado **antes** das 4 fontes de eventos (as FKs e `tipo_veiculo` NOT NULL dependem dele —
research R4), por upsert direto em `veiculo` sem passar por staging: é dado já canônico da
Prefeitura, não uma fonte heterogênea suja. `km_atual` do JSON é só o baseline inicial — o
cadastro **nunca** o rebaixa; só o R10 (abastecimento) o eleva.

## Vocabulário de motivos de rejeição (fechado — research R7)

`placa_invalida` · `data_ausente` · `data_invalida` · `valor_invalido` · `tipo_desconhecido` ·
`categoria_desconhecida` · `situacao_desconhecida` · `duplicado` · `veiculo_desconhecido` ·
`fonte_indisponivel`

Cada linha de `log_qualidade` guarda `fonte`, `registro_bruto` (a linha original serializada),
`motivo_rejeicao` e `carga_em` (correlaciona com o staging).

## `duplicado` × idempotência — a distinção que importa

- **`duplicado`** é *intra-lote*: a 2ª ocorrência da chave natural **na mesma carga** (as
  duplicatas do SQLite de licenciamento, multas repetidas no mesmo payload). Vai ao log.
- **Idempotência** é *entre ciclos*: um registro já consolidado que reaparece num ciclo
  posterior é **no-op silencioso** — as chaves UNIQUE do banco (contrato 002/ADR-004) o
  absorvem, e ele **não** vai ao log. Rodar o pipeline N vezes sobre os mesmos dados produz o
  mesmo estado nas consolidadas **e** no `log_qualidade` (SC-001).

## Resiliência por fonte (research R8)

Cada fonte roda isolada por `try/except`: se uma falha (endpoint fora, arquivo corrompido), a
falha vira uma linha `fonte_indisponivel` em `log_qualidade` (`situacao=indisponivel` no resumo)
e o ciclo **segue** para as demais (SC-005). O ciclo seguinte se recupera sozinho quando a fonte
volta. Uma linha corrompida *dentro* de um arquivo legível não é falha de fonte: é rejeição de
registro (motivos acima), e o resto do lote entra normalmente — nunca tudo-ou-nada.

> Exceção deliberada: o **cadastro não é isolado**. Banco inacessível ou `veiculos.json` ausente
> é erro estrutural (exit ≠ 0), não uma fonte a pular — sem cadastro nenhum evento tem FK válida.

## Testes

```bash
uv run pytest tests/test_pipeline.py -v
```

Cobre os normalizadores (T010) e as quatro user stories: extração bruta com rastreabilidade
(US1), qualidade/rejeição (US2/SC-002), idempotência e `km_atual` monotônico (US3/SC-001) e
resiliência por fonte (US4/SC-005). Roteiro manual de validação: `specs/003-pipeline-etl/quickstart.md`.
