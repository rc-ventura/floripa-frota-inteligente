# ADR-006: Idempotência do motor por INSERT em lote com `ON CONFLICT DO NOTHING` + delta de `COUNT` (em vez de SAVEPOINT por linha)

**Status**: Proposta — ratifica com o merge do MR da spec 004 em `dev`
**Data**: 2026-07-20
**Spec relacionada**: [004-motor-alertas](../../specs/004-motor-alertas/spec.md)
**Código**: `alertas/motor.py` (`_inserir_alertas`, `verificar_alertas`)

---

## Contexto

O motor de alertas precisa ser idempotente (FR-003/SC-002): rodando N vezes sobre o mesmo
estado, **zero** alertas ativos duplicados. A garantia de fundo é do banco — o índice único
parcial `ux_alerta_ativo (placa, tipo_gatilho, coalesce(limiar_id, -1)) WHERE situacao='ativo'`
(ADR-004) rejeita um segundo alerta ativo para a mesma chave. O contrato
(`contracts/motor_alertas.md` § Retorno) exige que `verificar_alertas()` devolva
`criados_km`, `criados_tempo`, `criados_dados_insuficientes` e `ja_ativos`, com a ressalva de
que as contagens venham de **inserts efetivos**, nunca de `rowcount` — porque o psycopg devolve
`-1` em `INSERT ... VALUES (multi) ON CONFLICT` (learning lesson 2026-07-19).

O pseudocódigo de projeto (data-model §3, R4; task T007) descreveu **um caminho** para isso:
INSERT por linha dentro de `session.begin_nested()` (SAVEPOINT); em `IntegrityError` do índice,
rollback do savepoint e `ja_ativos += 1`; em sucesso, `criados_<tipo> += 1`.

A implementação seguiu **outro caminho**, equivalente no resultado: INSERT em **lote agrupado por
`tipo_gatilho`** com `ON CONFLICT DO NOTHING`, contando `criados_<tipo>` pelo delta de `COUNT(*)`
antes/depois de cada grupo e `ja_ativos = total_de_candidatos − total_criados`. Os dois produzem
o mesmo estado no banco, os mesmos números no retorno e a mesma idempotência (provado em
`tests/test_alertas.py`). Este ADR registra a decisão de **manter o caminho em lote** e alinha os
documentos de projeto a ele.

## Decisão

A idempotência do motor é implementada por **INSERT em lote por `tipo_gatilho` com
`ON CONFLICT DO NOTHING`**, deixando o índice parcial `ux_alerta_ativo` rejeitar duplicata de
alerta ativo (no-op). As contagens do contrato derivam de **inserts efetivos**:

- `criados_<tipo>` = `COUNT(*)` depois − `COUNT(*)` antes do INSERT daquele grupo;
- `ja_ativos` = `len(candidatos) − (criados_km + criados_tempo + criados_dados_insuficientes)`;
- `rowcount` **nunca** é usado (evita o `-1` do psycopg — learning lesson "dois bancos-alvo").

Tudo dentro de uma transação (`engine.begin()`), garantindo o COMMIT (SQLAlchemy 2.0 `future`
não faz autocommit) e comportamento idêntico em SQLite e PostgreSQL 16.

**Por que o delta de `COUNT` é exato aqui — invariante "sem colisão intra-lote":** num único ciclo
de verificação não existem dois candidatos idênticos para a mesma chave
`(placa, tipo_gatilho, coalesce(limiar_id, -1))`:

- cada par avaliável `(placa, tipo)` gera no máximo um `km` **e** um `tempo` — gatilhos distintos,
  e cada tipo de manutenção tem `limiar_id` distinto (`UNIQUE(tipo_veiculo, tipo_manutencao)`);
- há no máximo **um** `dados_insuficientes` por veículo (`limiar_id` NULL → sentinela `-1`).

Logo, o único conflito possível é contra linhas persistidas em **ciclos anteriores** → o delta de
`COUNT` conta exatamente as novas inserções e o restante são ativos preexistentes (`ja_ativos`).

## Alternativas consideradas

### Alternativa A: SAVEPOINT por linha (o pseudocódigo R4/T007)

**Por que não foi escolhida como padrão**:
- Faz N INSERTs + N savepoints por ciclo (mais idas ao banco); o lote resolve em ≤3 statements
  (um por `tipo_gatilho`);
- Não traz benefício aqui: sem colisão intra-lote, a granularidade por linha é desnecessária.

**Mantida como plano de saída**: se o invariante "sem colisão intra-lote" deixar de valer (ver
condições abaixo), voltar à Alternativa A preserva a contagem exata sem depender de deltas.

### Alternativa B: contar por `rowcount`

**Por que não foi escolhida**: `cursor.rowcount` devolve `-1` em `INSERT` multi-VALUES com
`ON CONFLICT` no psycopg — contagem não confiável (learning lesson 2026-07-19). Rejeitada em
qualquer mecanismo.

## Consequências

### Aceitas

- Menos statements por ciclo; retorno em conformidade com o contrato
  (`veiculos_avaliados, criados_km, criados_tempo, criados_dados_insuficientes, ja_ativos`);
- Contagem dialeto-agnóstica por inserts efetivos, nunca `rowcount`.

### Trade-offs

- As contagens por tipo são **inferidas** do delta de `COUNT`, não observadas por linha: a
  correção depende do invariante "sem colisão intra-lote". Se, no futuro, o motor emitir dois
  candidatos para a mesma chave num único ciclo, o delta subcontaria os criados.

### Condições que invalidam esta decisão

Revisitar (e provavelmente migrar para a Alternativa A) se:

1. Passar a existir mais de um limiar por `(tipo_veiculo, tipo_manutencao)` (hoje `UNIQUE`), ou
2. `dados_insuficientes` deixar de ser um-por-veículo (ex.: um por `(placa, tipo)`), ou
3. Qualquer mudança que permita dois candidatos com a mesma
   `(placa, tipo_gatilho, coalesce(limiar_id, -1))` no mesmo ciclo.

### Caminho de migração

1. Trocar `_inserir_alertas` por laço `begin_nested()` por linha (Alternativa A);
2. Atualizar data-model §2–§3 (R4) e a task T007 no **mesmo MR**;
3. Os testes de `tests/test_alertas.py` já asseveram as **chaves do contrato** e a idempotência
   (SC-002), cobrindo os dois mecanismos sem alteração.

## Referências

- Contrato do motor: `specs/004-motor-alertas/contracts/motor_alertas.md` (§ Retorno)
- Data-model do motor: `specs/004-motor-alertas/data-model.md` (§2 invariantes, §3 R4)
- Learning lesson "dois bancos-alvo" (rowcount/`-1`): [valide o ciclo nos dois bancos-alvo](../learning-lessons/valide_o_ciclo_de_ponta_a_ponta_nos_dois_bancos_alvo.md)
- ADR relacionado: [ADR-004](ADR-004-null-em-chaves-de-upsert.md) (índice `ux_alerta_ativo` com `coalesce(limiar_id, -1)`)
