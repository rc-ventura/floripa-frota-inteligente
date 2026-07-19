# Valide o ciclo de ponta a ponta nos dois bancos-alvo: costuras entre fases e drivers escondem bugs que testes unitários não veem

**Context:** Descoberto na validação da Phase 4 (US2 — transformação de qualidade e carga) da spec 003, ao rodar o ciclo E→T→L completo primeiro no CLI real e depois em PostgreSQL 16 (container descartável). Dois bugs invisíveis para a suíte de testes existente: um `KeyError` na costura Extract→Transform e um `rowcount=-1` do psycopg que o SQLite mascarava.
**Date:** 2026-07-19
**Future intent:** Toda entrega de fase do pipeline (e do motor, spec 004) inclui uma passada de validação executando o ciclo real nos dois dialetos antes do commit; spec 007 deve rodar a suíte contra PostgreSQL no compose.

---

## Mental Model: os dois "ambientes confortáveis" que escondem bugs

Um teste que passa prova o que ele **exercita**, não o que o contrato **promete**. Nesta fase, dois confortos distintos esconderam um bug cada:

```
conforto 1: a costura entre fases          conforto 2: o dialeto único
┌──────────┐         ┌──────────┐          ┌────────────┐   ┌─────────────┐
│ Extract  │──lote──►│Transform │          │   SQLite    │   │ PostgreSQL  │
│ (Fase 3) │   ▲     │ (Fase 4) │          │ rowcount ok │   │ rowcount -1 │
└──────────┘   │     └──────────┘          └────────────┘   └─────────────┘
        escrito ANTES da interface              testes rodavam SÓ aqui
        que a Fase 4 assumiu existir            a demo roda AQUI
```

| Camada de validação | Onde atua | O que cobre | O que NÃO cobre |
|---|---|---|---|
| Testes unitários (T010) | funções puras | normalizadores, regras isoladas | integração entre estágios |
| Testes de aceitação por fase (T016/T021) | ciclo em SQLite | contrato observável no dialeto de dev | semântica específica de driver |
| Ciclo real via CLI (`python -m pipeline.run_etl`) | processo inteiro | wiring, exit codes, resumo impresso | outros dialetos |
| Ciclo nos dois bancos (D2) | SQLite **e** PostgreSQL | promessas do contrato em ambos os alvos | — |

A última linha é a única que valida o que a decisão D2 promete: *mesmo código, mesmo esquema, dois bancos*.

---

## Bug 1 — a costura: `KeyError: 'carga_em'` entre estágios escritos em fases diferentes

Os extratores (Fase 3) devolviam exatamente as 4 chaves do contrato público (`situacao`,
`extraidos`, `consolidados`, `rejeitados`); o orquestrador da Fase 4 assumiu um canal
interno que nunca existiu:

```python
resumo = extrair(engine)
carga_em = resumo.pop("carga_em")   # KeyError na 1ª fonte com novidade
```

Nenhum teste rodou o ciclo entre a escrita das duas metades — o crash só apareceu ao
executar `executar_ciclo()` de verdade.

**Correção**: o extrator passa a incluir `"carga_em"` no retorno (canal interno) e o
orquestrador extrai com `pop("carga_em", None)` **antes** de qualquer early-return —
a chave nunca vaza para o resumo público, e o contrato de 4 chaves continua intacto.

**Regra prática**: quando duas fases escrevem as metades de uma interface, o primeiro
teste a rodar depois do wiring é o ciclo inteiro — não a suíte unitária.

---

## Bug 2 — o dialeto: `rowcount=-1` do psycopg mascarado pelo SQLite

`rowcount` é uma promessa do DBAPI que nem todo driver cumpre em toda operação. Em
INSERT multi-VALUES com ON CONFLICT, o driver do SQLite reporta o número real; o
psycopg (PostgreSQL) devolve `-1` ("não determinável"):

```python
with engine.begin() as conn:
    return conn.execute(stmt).rowcount   # SQLite: N · PostgreSQL: -1
```

Os dados chegavam corretos ao PG (integridade ok) — mas o resumo do ciclo violava o
contrato (`consolidados` = "linhas que chegaram às consolidadas"), quebraria a
invariante de conservação (`extraidos == consolidados + rejeitados`) e mentiria no
diagnóstico do agendador (spec 004). Só apareceu porque a validação subiu um Postgres
descartável e comparou o resumo.

**Correção** — semântica por natureza da tabela, sem depender de driver:

```python
# Fatos (do_nothing): delta de COUNT na MESMA transação — exato e dialeto-agnóstico
def _insert_contando_delta(engine, tabela, stmt) -> int:
    with engine.begin() as conn:
        antes = conn.execute(select(func.count()).select_from(tabela)).scalar()
        conn.execute(stmt)
        return conn.execute(select(func.count()).select_from(tabela)).scalar() - antes

# Dimensões (do_update por placa): cada linha válida insere OU atualiza a sua placa
# → consolidados = len(validos), por definição (delta subcontaria updates)
```

Alternativas rejeitadas: `RETURNING` + contagem (traz todas as linhas só para contar);
confiar no `rowcount` quando `>= 0` (mantém caminho dependente de driver); pré-consultar
conflitos em Python (reimplementa a chave UNIQUE fora do banco — research R3).

---

## Exemplos no projeto

- `pipeline/run_etl.py::_processar_fonte` — `pop("carga_em", None)` antes do early-return.
- `pipeline/load/upsert.py::_insert_contando_delta` — contagem por delta nos fatos.
- `pipeline/load/upsert.py::upsert_licenciamento` e `pipeline/load/cadastro.py` —
  `len(validos)` nas dimensões.
- Roteiro que pegou os dois: ciclo CLI em `db/frota.db` + container `postgres:16`
  (quickstart da spec 003, Cenários 1–4 + variante PG do Cenário 5 da spec 002).

**Responsibility split:**
- Suíte pytest (SQLite): regressão rápida do contrato observável.
- Validação de fase: ciclo real nos **dois** dialetos antes do commit.

---

## Relation to ADRs and next steps

- **Arquitetura D2** (SQLite dev ↔ PostgreSQL demo via `DATABASE_URL`): a promessa "troca sem reescrever código" só é verdadeira se for **exercitada** — o dialeto de dev não é prova do dialeto da demo.
- **ADR-004 / research R3 da spec 003**: reforça a regra "deixe o banco decidir o conflito" — a correção conta resultados, não reimplementa chaves.
- **Learning lesson anterior** ([proteja a âncora do ruído](./proteja_a_ancora_do_ruido_e_teste_o_invariante_negativo.md)): mesmo padrão geral — teste o que o contrato promete, não o que o ambiente de teste por acaso entrega.
- **Próximo passo concreto**: na spec 007 (empacotamento), rodar a suíte contra o PostgreSQL do compose (não só SQLite) e manter a variante PG do quickstart como cenário obrigatório de release.
