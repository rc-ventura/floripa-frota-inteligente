# Quickstart — Validação do Motor de Alertas (Spec 004)

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contrato**: [contracts/motor_alertas.md](./contracts/motor_alertas.md)

Roteiro de validação de ponta a ponta que prova o motor. **Não** contém implementação — os
detalhes de regra estão em [data-model.md](./data-model.md) §3 e no contrato. Cada cenário mapeia a
uma User Story e a um Success Criteria da spec.

## Pré-requisitos

- Python 3.12 + ambiente do repositório (`uv sync`); `apscheduler` já está no `pyproject.toml`.
- Esquema criado e limiares semeados: `python -m db.init_db` (contrato spec 002).
- Pipeline disponível: `python -m pipeline.run_etl` funcional (spec 003, entregue).

```bash
# ambiente limpo de dev (SQLite)
uv sync
python -m db.init_db            # cria esquema + seed de limiar_config (idempotente)
```

---

## Caminho rápido — subir o app completo em 1 processo (scheduler)

O `scheduler.py` costura **ETL → Motor** num ciclo único e ordenado (arquitetura §8) e roda o
**primeiro ciclo imediatamente** (não espera 1 intervalo). É o "app completo" da PoC hoje — os
painéis (specs 005/006) ainda não entram. Verificado nas duas pontas (CLI + scheduler).

```bash
uv sync
python -m db.init_db                              # esquema + limiares (idempotente)
CICLO_INTERVALO_SEGUNDOS=5 python scheduler.py    # sobe o ciclo; Ctrl-C / SIGTERM encerra limpo
```

Em **outro terminal**, faça o gesto da demo e veja o alerta surgir sozinho no próximo tick:

```bash
cp data/seeds/gatilho_demo_abastecimento.csv data/inbox/   # eleva o km_atual de RLL8062
sleep 6                                                     # ~1 ciclo
python -c "from sqlalchemy import text; from db.config import get_engine; \
print(get_engine().connect().execute(text(\"SELECT placa,tipo_gatilho,situacao,detalhe FROM alerta WHERE situacao='ativo' ORDER BY id\")).all())"
```

**Esperado** — nos logs do scheduler, `ciclo completo: etl=… motor={… criados_km/criados_tempo …}`;
o alerta de `TND8453` (tempo) já no 1º ciclo e o de `RLL8062` (km) no ciclo após o depósito do CSV,
sem nenhuma ação manual entre ticks. Uma fonte fora do ar aparece como `indisponivel` e **não**
interrompe o motor (US5.3).

> Prefere passo a passo (cada camada isolada)? Os Cenários 1–6 abaixo cobrem cada User Story/SC
> individualmente, chamando `python -m pipeline.run_etl` e `python -m alertas.motor` à mão.

---

## Cenário 1 — Alerta por tempo aparece sozinho (US2 · SC-006)

O veículo `TND8453` (leve) nasce com ~166 dias desde a última troca de óleo; limiar
`180 − 15 = 165`. Sem nenhuma manipulação, a 1ª verificação já dispara.

```bash
python -m pipeline.run_etl      # consolida os seeds
python -m alertas.motor         # 1 verificação
```

**Esperado**: resumo com `criados_tempo ≥ 1`. No banco existe uma linha em `alerta` com
`placa='TND8453'`, `tipo_gatilho='tempo'`, `situacao='ativo'`, `limiar_id` apontando para o limiar
`(leve, troca_oleo)`.

```bash
python -c "from sqlalchemy import text; from db.config import get_engine; \
print(get_engine().connect().execute(text(\"SELECT placa,tipo_gatilho,situacao FROM alerta WHERE tipo_gatilho='tempo'\")).all())"
```

---

## Cenário 2 — Disparo por km ao vivo (US1 · SC-001) — o momento da demo

O veículo `RLL8062` (leve) está ~600 km da janela. Depositar o CSV de gatilho eleva `km_atual`; no
ciclo seguinte o motor cruza a antecedência.

```bash
# 1) estado antes: nenhum alerta km para RLL8062
python -m pipeline.run_etl && python -m alertas.motor

# 2) gesto da demo: depositar o gatilho na pasta monitorada
cp data/seeds/gatilho_demo_abastecimento.csv data/inbox/

# 3) ciclo seguinte: ETL ingere o km novo, motor dispara
python -m pipeline.run_etl && python -m alertas.motor
```

**Esperado**: após o passo 3, `criados_km ≥ 1` e existe `alerta` com `placa='RLL8062'`,
`tipo_gatilho='km'`, `situacao='ativo'` — **antes** do vencimento real (métrica binária do briefing).

---

## Cenário 3 — Idempotência: 10 verificações, zero duplicatas (US3 · SC-002)

```bash
python -m pipeline.run_etl
for i in $(seq 1 10); do python -m alertas.motor >/dev/null; done
python -c "from sqlalchemy import text; from db.config import get_engine; \
print('ativos:', get_engine().connect().execute(text(\"SELECT COUNT(*) FROM alerta WHERE situacao='ativo'\")).scalar())"
```

**Esperado**: a contagem de alertas **ativos** é a mesma da 1ª verificação (não cresce a cada
rodada); do 2º ciclo em diante o resumo mostra `criados_* = 0` e `ja_ativos > 0`.

**Histórico/recorrência**: resolver um alerta manualmente (`UPDATE alerta SET situacao='resolvido'
WHERE id=…`) e rodar de novo — o resolvido **permanece** consultável e, se a condição persistir,
uma **nova** linha `ativo` é criada (nunca há DELETE).

---

## Cenário 4 — Dados insuficientes viram alerta, não silêncio (US4 · SC-003)

Inserir um veículo cujo tipo tenha limiar mas sem manutenção registrada (ou com `km_atual` menor
que o `km_no_momento` da última manutenção) e verificar.

**Esperado**: existe exatamente **um** `alerta` `dados_insuficientes` para essa placa, com
`limiar_id IS NULL` e `detalhe` não-vazio explicando a causa (ex.: `"troca_oleo: sem manutenção
registrada"` ou `"revisao_geral: km não confiável (…)"`). Nenhum veículo elegível fica sem linha em
`alerta` — 100% dos não-avaliáveis aparecem.

```bash
python -c "from sqlalchemy import text; from db.config import get_engine; \
print(get_engine().connect().execute(text(\"SELECT placa,detalhe FROM alerta WHERE tipo_gatilho='dados_insuficientes'\")).all())"
```

---

## Cenário 5 — Edição de limiar ao vivo muda a próxima verificação (US1.3 · SC-004)

```bash
# baixar a antecedência/limite de (leve, troca_oleo) direto na tabela (sem reiniciar nada)
python -c "from sqlalchemy import text; from db.config import get_engine; \
e=get_engine(); c=e.connect(); c.execute(text(\"UPDATE limiar_config SET limite_km=limite_km-2000 WHERE tipo_veiculo='leve' AND tipo_manutencao='troca_oleo'\")); c.commit()"
python -m alertas.motor
```

**Esperado**: a verificação seguinte usa o novo valor **imediatamente** (o motor relê
`limiar_config` a cada verificação — sem cache) e o conjunto de alertas reage à mudança, sem
reiniciar processo nem alterar código.

---

## Cenário 6 — Ciclo agendado de ponta a ponta (US5 · SC-005)

```bash
CICLO_INTERVALO_SEGUNDOS=5 python scheduler.py &   # intervalo curto só para validar
sleep 6
cp data/seeds/gatilho_demo_abastecimento.csv data/inbox/
sleep 12                                           # 1–2 ticks: ETL ingere e motor dispara
# conferir no banco que o alerta de RLL8062 surgiu sem nenhuma ação manual entre ticks
kill %1
```

**Esperado**: depositar o CSV resulta em alerta no banco **em ≤1 ciclo completo**, sem intervenção
manual. Trocar `CICLO_INTERVALO_SEGUNDOS` altera a cadência **sem** mudar código (SC-005). Com uma
fonte do ETL fora do ar, o motor ainda roda sobre o estado consolidado disponível (US5.3).

---

## Suíte automatizada (critério de aceite do kanban — SC-006/FR-008)

`tests/test_alertas.py` cobre: as **regras puras** (`alertas/regras.py`), o **contrato do retorno**,
disparo por **km** (+ edição de limiar ao vivo), disparo por **tempo**, **idempotência** (10× → 0
duplicatas) + histórico/recorrência, **dados_insuficientes** (4 casos) e o **ciclo agendado** (US5:
`scheduler.executar_ciclo_e_verificar`, intervalo por env var, fonte fora do ar). Fixture herdada de
`tests/test_pipeline.py` (SQLite em `tmp_path` + `db.init_db.main()`); `hoje` é injetado para
determinismo (research R3); os veículos/limiares de referência são lidos dos seeds, sem valores
mágicos no teste.

```bash
uv run pytest tests/test_alertas.py -q
```

**Esperado**: todos passam.

---

## Validação nos dois dialetos (learning lesson "dois bancos-alvo") — obrigatória antes do commit

A suíte roda em SQLite; a demo roda em PostgreSQL 16. `tests/test_alertas.py` não cobre Postgres
diretamente (as fixtures fixam `DATABASE_URL` para SQLite em `tmp_path`, por isolamento/velocidade)
— por isso os Cenários 1–6 são repetidos **manualmente via CLI real** contra um Postgres descartável,
o mesmo caminho que a demo usa. O no-op de conflito (INSERT em lote com `ON CONFLICT DO NOTHING`
sobre `ux_alerta_ativo`, **ADR-006**) e a contagem de criados (delta de `COUNT`, nunca `rowcount`)
devem se comportar **igual** nos dois dialetos:

```bash
docker run --rm -d --name frota-pg -e POSTGRES_PASSWORD=frota -e POSTGRES_DB=frota -p 5432:5432 postgres:16
export DATABASE_URL="postgresql+psycopg://postgres:frota@localhost:5432/frota"
python -m db.init_db
python -m pipeline.run_etl && python -m alertas.motor             # Cenários 1–2
for i in $(seq 1 10); do python -m alertas.motor >/dev/null; done # Cenário 3: 0 duplicatas
CICLO_INTERVALO_SEGUNDOS=5 python scheduler.py                    # Cenário 6 (Ctrl-C/SIGTERM encerra)
docker rm -f frota-pg
```

**Validado (2026-07-21)**: os 6 cenários rodaram nos dois dialetos com resultados **idênticos**
(mesmos `criados_km`/`criados_tempo`/`criados_dados_insuficientes`/`ja_ativos` em cada passo):
`criados_tempo=1` isolado no 1º ciclo (Cenário 1); `criados_km=1` após o gatilho, sem intervenção
manual (Cenário 2); **2 → 2** alertas ativos em 10 rodadas extras — a prova de que o delta de
`COUNT` não sofre do `rowcount=-1` do psycopg em multi-VALUES `ON CONFLICT` (Cenário 3, o mais
crítico do dialeto); 1 `dados_insuficientes` por veículo com `limiar_id IS NULL` (Cenário 4);
`criados_km=11` refletindo a edição ao vivo do limiar, sem reiniciar nada (Cenário 5); `scheduler.py`
com 1ª execução imediata, 2º tick idempotente e shutdown limpo em SIGTERM (Cenário 6).
