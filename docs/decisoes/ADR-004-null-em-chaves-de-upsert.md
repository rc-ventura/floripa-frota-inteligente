# ADR-004: Tratamento de NULL em chaves de unicidade/upsert das consolidadas (convenção coalesce-sentinela)

**Status**: Proposta — ratifica com o merge do MR da spec 002 em `dev`
**Data**: 2026-07-17
**Spec relacionada**: [002-modelo-dados-banco](../../specs/002-modelo-dados-banco/spec.md)
**Código**: `db/models.py` (índices `ux_alerta_ativo`, `ux_multa_upsert`), `db/migrations/versions/0002_ux_multa_upsert.py`

---

## Contexto

Em SQL, `NULL ≠ NULL`: uma constraint UNIQUE que inclui coluna anulável **não** rejeita duas
linhas idênticas quando essa coluna é NULL — ambas entram silenciosamente, em SQLite e em
PostgreSQL. O esquema da spec 002 tem três chaves de upsert nessa situação, e a revisão SDD
(ciclo 1) encontrou-as resolvidas de **três formas inconsistentes**:

| Tabela | Coluna anulável na chave | Comportamento encontrado no ciclo 1 |
|---|---|---|
| `alerta` | `limiar_id` (NULL p/ `dados_insuficientes`) | correto — `coalesce(limiar_id, -1)` no índice parcial `ux_alerta_ativo` faz NULLs colidirem |
| `multa` | `condutor_pseudo` (NULL quando fonte não informa) | **defeito** — duas multas idênticas sem condutor entravam duplicadas, contradizendo a promessa do contrato ("a 2ª vai para `log_qualidade` com motivo `duplicado`") e a idempotência (constitution VII); risco de multa contada 2× no painel de custos da demo |
| `abastecimento` | `km_hodometro` (NULL permitido pelo ADR-002) | deliberado mas mal documentado — research R7 diz "NULLs de km não conflitam; dedup fina fica no pipeline", porém o contrato não repetia a ressalva |

Sem uma convenção, um leitor futuro (specs 003/004) não consegue distinguir qual NULL-não-colide
é decisão e qual é bug.

## Decisão

**Toda coluna anulável que participe de chave de unicidade/upsert deve seguir exatamente um
de dois caminhos, ambos explícitos:**

1. **Coalesce-para-sentinela** (padrão preferido): a chave vira índice único de expressão com
   `coalesce(coluna, <sentinela>)`, fazendo NULLs colidirem entre si. A sentinela deve ser um
   valor impossível no domínio da coluna (`-1` para FKs inteiras, `''` para pseudônimos
   `COND-NNN`).
2. **Dedup no pipeline** (exceção justificada): o NULL não colide no banco **e** o contrato
   (`contracts/esquema_tabelas.md`) declara explicitamente que a deduplicação desse caso é
   responsabilidade do pipeline, com o racional.

Aplicação por tabela:

- `alerta` → caminho 1: `ux_alerta_ativo (placa, tipo_gatilho, coalesce(limiar_id, -1)) WHERE situacao='ativo'` (já existia; research R6).
- `multa` → caminho 1 (corrigido na **migration 0002**): a UNIQUE `(placa, data, valor, condutor_pseudo)` foi substituída por `ux_multa_upsert (placa, data, valor, coalesce(condutor_pseudo, ''))` — multa sem condutor agora colide, honrando a promessa do contrato.
- `abastecimento` → caminho 2: `(placa, data, km_hodometro)` mantém NULL-km sem colisão. Dois abastecimentos sem km no mesmo dia podem ser dois eventos reais (não há como distingui-los na fonte); forçar colisão rejeitaria um abastecimento legítimo. A ressalva agora consta do contrato e do data-model.
- `manutencao`, `licenciamento`, `veiculo` → chaves 100% NOT NULL; a questão não se aplica.

Regra de teste (learning lesson "invariante negativo"): cada chave de upsert ganha teste
positivo (duplicata completa colide) **e** negativo (o caso NULL se comporta exatamente como o
contrato declara) — `tests/test_db.py::test_chaves_upsert_consolidadas`.

## Alternativas consideradas

### Alternativa A: colunas NOT NULL com sentinela armazenada (ex.: `condutor_pseudo = ''`)

**Por que não foi escolhida**:
- Polui o dado consolidado com valores mágicos que os painéis (specs 005/006) teriam de
  filtrar em toda consulta;
- `NULL` é a representação semanticamente correta de "fonte não informou".

### Alternativa B: deduplicação inteiramente no pipeline (sem constraint no banco)

**Por que não foi escolhida**:
- Research R7 já rejeitou: upsert idempotente exige chave **no banco**; regra só no código é
  contrato implícito e não resiste a concorrência;
- Violaria constitution VII (idempotência garantida por construção, não por disciplina).

## Consequências

### Aceitas

- O contrato volta a ser verdadeiro: a 2ª multa idêntica (com ou sem condutor) é rejeitada
  pelo banco e vai para `log_qualidade` — sem dupla contagem no painel de custos;
- Convenção única e nomeada para specs futuras: quem adicionar chave com coluna anulável
  sabe que precisa escolher (e documentar) um dos dois caminhos.

### Trade-offs

- Índices de expressão não são refletidos pelo autogenerate do Alembic em SQLite — toda
  mudança neles é migration escrita à mão (mesmo caso do `ux_alerta_ativo`);
- Duas multas **genuinamente distintas** de mesmo valor, mesma placa, mesmo dia e ambas sem
  condutor são indistinguíveis e a 2ª será rejeitada — limitação aceita da PoC, já declarada
  no contrato (a chave natural completa, `codigo_infracao`, é fonte-apenas por ADR-003).

### Condições que invalidam esta decisão

Esta decisão deve ser **revisitada** se:

1. A consolidada `multa` passar a persistir um identificador natural da infração
   (ex.: `codigo_infracao` + hora) — a chave pragmática com coalesce deixa de ser necessária;
2. O pipeline (spec 003) implementar dedup probabilística própria que torne a colisão no
   banco redundante ou conflitante.

### Caminho de migração

1. Nova migration Alembic derrubando/recriando o índice de expressão;
2. Atualizar `contracts/esquema_tabelas.md`, `data-model.md` e research R7 no **mesmo MR**
   (regra de estabilidade do contrato);
3. Ajustar `tests/test_db.py::test_chaves_upsert_consolidadas` para o novo invariante.

## Referências

- Revisão SDD ciclo 1: `reports/sdd-final-review/002-modelo-dados-banco/cycle-1-20260717-0903.md`
- Research R6 (índice parcial de alerta) e R7 (chaves de upsert): `specs/002-modelo-dados-banco/research.md`
- Learning lesson: [Proteja a âncora do ruído: teste o invariante negativo](../learning-lessons/proteja_a_ancora_do_ruido_e_teste_o_invariante_negativo.md)
- ADRs relacionados: [ADR-002](ADR-002-persistir-km-hodometro-abastecimento.md) (origem da anulabilidade de `km_hodometro`), [ADR-003](ADR-003-calibracao-realismo-fontes-simuladas.md) (por que `codigo_infracao` é fonte-apenas)
