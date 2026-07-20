# ADR-005: Política de sobrescrita/merge no upsert de dimensões (`on_conflict_do_update`)

**Status**: Proposta — ratifica com o merge do MR da spec 003 em `dev`
**Date**: 2026-07-20
**Related spec**: [003-pipeline-etl](../../specs/003-pipeline-etl/spec.md)
**Code**: `pipeline/load/upsert.py` (`upsert_licenciamento`), `pipeline/load/cadastro.py` (`carregar_cadastro`)

---

## Context

O pipeline (spec 003) carrega duas **dimensões** por upsert com `on_conflict_do_update`
(a placa é 1:1 com o veículo/licenciamento): `veiculo` (cadastro) e `licenciamento`. O
[ADR-004](ADR-004-null-em-chaves-de-upsert.md) já governa as **chaves** de conflito dessas
cargas — mas não diz nada sobre a **cláusula SET**: *quais colunas vencem quando a chave
colide, e o que fazer quando o valor entrante é NULL*.

A revisão SDD (ciclo 1 da spec 003) encontrou essa segunda decisão **já materializada de
forma inconsistente** entre as duas dimensões — exatamente o tipo de divergência silenciosa
que originou o ADR-004, reaparecendo agora no eixo do update-SET:

| Dimensão | Coluna | Comportamento encontrado |
|---|---|---|
| `veiculo` (`carregar_cadastro`) | `km_atual` | **excluído do SET** — o cadastro nunca o toca; só o R10 (MAX do hodômetro) o eleva, monotônico |
| `veiculo` | `modelo`, `ano`, `secretaria` | sobrescritos **incondicionalmente** — um recarregamento com esses campos NULL zeraria um valor já persistido |
| `licenciamento` (`upsert_licenciamento`) | `vencimento`, `situacao` | sobrescritos **incondicionalmente** — idem: um lote futuro com `vencimento` NULL zeraria o vencimento consolidado, **sem** registro em `log_qualidade` (regressão silenciosa — viola constitution II) |
| ambas | `fonte_origem` | sobrescrito incondicionalmente (correto — reflete a carga mais recente) |

Dois cenários concretos, ambos **não disparáveis com o seed fixo hash-gated** (a fonte é lida
uma vez por conteúdo — R1), mas latentes assim que a fonte for atualizada ou dado real for
ingerido:

- **Cross-lote (Devin-A)**: se o `.sqlite` de licenciamento for substituído (novo hash) com
  uma placa de `vencimento` **mais antigo**, ele sobrescreve o mais recente já consolidado. A
  regra "vencimento mais recente vence" do transform (research R3) é imposta **só intra-lote**
  (`pipeline/transform/qualidade.py:265`), nunca contra a linha já persistida.
- **NULL entrante (Devin-B)**: se a única linha de uma placa num lote futuro tem
  `vencimento IS NULL`, a sobrevivente é NULL e o upsert **zera** um `vencimento` não-nulo já
  consolidado — perda silenciosa de dado, sem trilha.

Sem uma convenção nomeada, o motor da spec-004 (que escreve `alerta` via `do_update`) e os
painéis das specs 005/006 vão re-derivar cada um a sua política.

## Decision

**A cláusula SET de todo upsert de dimensão segue uma de três políticas explícitas, escolhida
por coluna:**

1. **`monotonic-exclude`** — a coluna é **omitida do SET**; seu valor só muda por lógica
   dedicada, nunca regride. Aplica-se a agregados acumulados. Caso: `veiculo.km_atual`
   (só o R10 o eleva).
2. **`coalesce-preserva-não-nulo`** (padrão para campos descritivos anuláveis não-chave): a
   coluna vira `col = COALESCE(excluded.col, <tabela>.col)`. Um valor entrante **não-nulo
   vence** (last-write-wins); um entrante **NULL preserva** o valor já persistido — nunca o
   apaga. Casos: `veiculo.modelo/ano/secretaria`, `licenciamento.vencimento/situacao`.
3. **`last-write-wins`** — sobrescrita incondicional. Reservado para metadados de proveniência
   que **devem** refletir a carga mais recente. Caso: `fonte_origem`.

```python
# licenciamento (dimensão) — coalesce-preserva-não-nulo nos descritivos, LWW no fonte_origem
stmt.on_conflict_do_update(
    index_elements=["placa"],
    set_={
        "vencimento":   func.coalesce(stmt.excluded.vencimento, Licenciamento.vencimento),
        "situacao":     func.coalesce(stmt.excluded.situacao,   Licenciamento.situacao),
        "fonte_origem": stmt.excluded.fonte_origem,   # last-write-wins (proveniência)
    },
)
# veiculo (cadastro) — km_atual NÃO entra no SET (monotonic-exclude, R10)
```

**Trade-off cross-lote aceito (Devin-A)**: com `coalesce-preserva-não-nulo`, um valor entrante
não-nulo **sempre vence**, inclusive um `vencimento` mais antigo numa exportação posterior.
Isso é **deliberado**: uma dimensão reflete o **último estado do system-of-record legado** —
se o sistema de origem regrediu um dado, a consolidada acompanha. A política só protege contra
**apagamento por NULL** (Devin-B), não contra atualização por valor mais antigo (que é uma
atualização legítima da fonte, não uma perda).

## Alternatives considered

### Alternativa A: `last-write-wins` em tudo (o que estava implementado)

**Por que não foi escolhida**:
- Zera silenciosamente um valor persistido quando o entrante é NULL (Devin-B) — perda de dado
  sem `log_qualidade`, violando a rastreabilidade da constitution II;
- Já conflitava com o `monotonic-exclude` de facto do `km_atual`, deixando o esquema com duas
  políticas não nomeadas (o problema que o ADR-004 mandou não repetir).

### Alternativa B: rejeitar (`log_qualidade`) todo lote que traga NULL sobre um valor não-nulo

**Por que não foi escolhida**:
- Um NULL numa dimensão normalmente significa "a fonte não informou desta vez", não "erro" —
  tratá-lo como rejeição encheria o log de ruído e exigiria intervenção para um caso benigno;
- `COALESCE` resolve o mesmo risco (não perder o dado) sem rejeição — mais simples
  (constitution VII).

### Alternativa C: versionar histórico da dimensão (SCD tipo 2)

**Por que não foi escolhida**:
- Complexidade desproporcional ao PoC (linha nova por mudança, colunas de vigência); as
  consolidadas da PoC guardam o estado corrente, não a série temporal da dimensão;
- Fica documentada como evolução caso a auditoria de mudanças de cadastro seja exigida.

## Consequences

### Aceitas

- Uma convenção única e nomeada para todo upsert de dimensão — o motor (004) e os painéis
  (005/006) herdam a regra em vez de re-inventá-la;
- Um NULL entrante nunca mais apaga um valor consolidado não-nulo (fecha Devin-B) — sem
  regressão silenciosa, honrando a constitution II;
- `km_atual` permanece monotônico por construção (o cadastro não pode rebaixá-lo).

### Trade-offs

- Um valor não-nulo **mais antigo** numa carga posterior ainda sobrescreve o mais recente
  (Devin-A) — aceito como "a dimensão reflete o último estado da fonte"; a distinção
  decisão-vs-bug fica registrada aqui para o leitor futuro;
- `COALESCE` em índice de expressão não é refletido pelo autogenerate do Alembic, mas isto é
  cláusula SET de runtime (não vai para migration) — sem impacto de schema.

### Condições que invalidam esta decisão

Esta decisão deve ser **revisitada** se:

1. A PoC passar a exigir **auditoria de mudanças** de uma dimensão (cadastro ou licenciamento)
   — aí a Alternativa C (SCD tipo 2) entra;
2. Uma fonte de dimensão passar a ser **autoritativa para apagar** (um NULL significar
   deliberadamente "remova este dado") — o `coalesce-preserva` deixaria de valer para ela.

### Caminho de migração

1. Ajustar `upsert_licenciamento` (`vencimento`, `situacao`) e `carregar_cadastro`
   (`modelo`, `ano`, `secretaria`) para `func.coalesce(excluded.col, tabela.col)`;
2. Teste de regressão: um lote com campo anulável NULL **não** zera o valor persistido
   não-nulo (`tests/test_pipeline.py`);
3. `km_atual` e `fonte_origem` permanecem como estão (monotonic-exclude / last-write-wins).

## References

- Revisão SDD ciclo 1: `reports/sdd-final-review/003-pipeline-etl/cycle-1-20260720-0710.md`
  (achados Devin-A e Devin-B, síntese do Tech Leader)
- Research R3/R4 da spec 003: `specs/003-pipeline-etl/research.md` (dedup por vencimento mais
  recente intra-lote; cadastro sem staging)
- ADR relacionado: [ADR-004](ADR-004-null-em-chaves-de-upsert.md) (governa as **chaves** de
  upsert; este ADR governa a **cláusula SET**)
- Constitution II (rastreabilidade — rejeição/perda nunca silenciosa) e VII (simplicidade)
