# Phase 0 — Research: Motor de Alertas Preventivos e Agendamento

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Date**: 2026-07-20

Objetivo: resolver toda incerteza técnica antes do design. Cada decisão cita o requisito/ADR
que a ancora. Não há `NEEDS CLARIFICATION` remanescente — as dependências (specs 002 e 003)
estão entregues e seus contratos fixam o esquema e o ponto de entrada do ciclo.

---

## R1 — Agendador embutido e ciclo único ordenado (FR-006, US5, D4)

**Decisão**: usar **APScheduler** (`BlockingScheduler`) em `scheduler.py` na raiz, com **um único
job** que executa, em sequência, `executar_ciclo()` (spec 003) e depois `verificar_alertas()`
(esta spec). Intervalo por `IntervalTrigger(seconds=intervalo_ciclo_segundos())`. Guardas contra
sobreposição: `max_instances=1` e `coalesce=True` (um ciclo por vez — o contrato da spec 003 §
Concorrência exige isso; o motor herda a garantia).

**Racional**: D4 já escolheu APScheduler (zero infra extra, open source, portável — constitution
VII). Um único job ordenado garante que a verificação de alertas lê o estado **após** a carga do
mesmo ciclo (arquitetura §8; edge case "ciclo do motor coincidindo com o ETL"). `max_instances=1`
+ `coalesce=True` impedem que um ciclo lento seja atropelado pelo próximo — mantém a idempotência
simples (sem concorrência real de escrita em `alerta`).

**Resiliência (US5.3 / SC-005 da spec 003)**: `executar_ciclo()` já isola falha por fonte e
retorna código 0; o job chama `verificar_alertas()` de qualquer forma, sobre o estado consolidado
disponível. Se `executar_ciclo()` levantar erro estrutural (banco inacessível), o job registra e
segue para o próximo tick (o scheduler não morre) — o motor não roda nesse tick por não haver
banco.

**Dependência a adicionar**: `apscheduler>=3.10,<4` (série 3.x estável, publicada há muito;
evita a 4.x ainda em beta). Adicionar com `uv add apscheduler` (atualiza `pyproject.toml` + `uv.lock`).

**Alternativas consideradas**:
- `cron` do SO / systemd timers — rejeitado por D4 (infra externa, não portável para o contêiner
  único da PoC; não nasce com o processo).
- Airflow/Prefect — rejeitado por D4 (sofisticação desproporcional à PoC; documentado como
  evolução de produção).
- `while True: sleep(intervalo)` caseiro — rejeitado: reimplementa (mal) coalescing, tratamento de
  drift e shutdown limpo que o APScheduler já dá.

---

## R2 — Ponto de entrada do motor e assinatura (FR-001, contrato)

**Decisão**: `alertas/motor.py` expõe `verificar_alertas(hoje: date | None = None) -> dict`,
importável (o scheduler agenda por import, como a spec 003 fez com `executar_ciclo`), **e** um
CLI `python -m alertas.motor` que imprime o resumo e sai com `0` (erro estrutural → `≠0`),
espelhando `pipeline/run_etl.py`.

**Retorno (dicionário de diagnóstico, só para log do agendador — não para painéis)**:

```python
{
  "veiculos_avaliados": int,     # veículos percorridos
  "criados_km": int,             # novos alertas km neste ciclo
  "criados_tempo": int,          # novos alertas tempo
  "criados_dados_insuficientes": int,
  "ja_ativos": int,              # colisões tratadas como no-op (idempotência)
}
```

**Racional**: simetria com o contrato da spec 003 (`executar_ciclo()` importável + CLI) facilita o
agendamento e o teste. Painéis (005/006) leem **só o banco** (constitution VI) — este retorno é
diagnóstico, nunca fonte de verdade.

**Alternativas**: classe `MotorAlertas` com estado — rejeitada; o motor é sem estado por design
(lê tudo do banco a cada verificação, SC-004). Função pura + banco é mais simples (VII).

---

## R3 — "Hoje" injetável para determinismo dos testes (US2, SC-001)

**Decisão**: `verificar_alertas(hoje=None)` usa `hoje = hoje or date.today()`. Testes passam uma
data fixa; a demo usa `date.today()` (os seeds são regenerados com data-âncora do dia da
apresentação — arquitetura §5.2, spec 001/007), então o veículo B (166 dias) cai sozinho no 1º
ciclo sem manipulação.

**Racional**: o gatilho por tempo depende de "hoje"; sem injeção, o teste seria não-determinístico
(dependeria do relógio da máquina de CI). Injeção é a forma mínima e testável de manter a regra
como dado (a antecedência/limite vêm de `LIMIAR_CONFIG`; só o "agora" é do relógio).

**Alternativas**: `freezegun`/mock de `date.today` — dependência a mais para o que um parâmetro
opcional resolve (VII).

---

## R4 — No-op de duplicata idempotente e dialeto-agnóstico (FR-003, SC-002, ADR-004)

**Decisão**: o motor **deixa o banco decidir o conflito**. Para cada alerta candidato, tenta
inserir dentro de um **SAVEPOINT** (`session.begin_nested()`); se o índice único parcial
`ux_alerta_ativo` (`placa, tipo_gatilho, coalesce(limiar_id,-1)) WHERE situacao='ativo'`) rejeitar
com `IntegrityError`, faz rollback do savepoint e conta como `ja_ativos` (no-op). Inserts
bem-sucedidos são contados diretamente (savepoint que fez commit) — contagem **não** depende de
`rowcount`.

**Racional**:
- O índice único parcial já existe no esquema (spec 002, research R6; ADR-004 caminho 1) e é a
  fonte de verdade da unicidade. Reimplementar a chave em Python (pré-SELECT do par) é
  explicitamente rejeitado pela learning lesson e pela research R3 da spec 003 ("deixe o banco
  decidir o conflito").
- O caminho SAVEPOINT + `IntegrityError` funciona **idêntico em SQLite e PostgreSQL** — não depende
  de inferência de índice de expressão parcial pelo `on_conflict_do_nothing` (que é frágil com
  `coalesce(...)` e cláusula `WHERE`). Atende diretamente a learning lesson "valide nos dois
  bancos-alvo".
- Contar por savepoint bem-sucedido (ou por delta de `COUNT` na mesma transação) evita o
  `rowcount=-1` do psycopg que o SQLite mascara (Bug 2 da learning lesson).

**Semântica do `dados_insuficientes` na chave**: `limiar_id` é NULL → `coalesce(limiar_id,-1) = -1`,
logo só existe **um** `dados_insuficientes` ativo por placa. Reexecução é no-op; o `detalhe` **não**
faz parte da chave e **não** é atualizado num no-op (mantém idempotência estrita — 0 escritas na 2ª
passada; ver R6).

**Alternativas**:
- `insert(...).on_conflict_do_nothing(index_elements=[...], index_where=text("situacao='ativo'"))`
  — funciona no PostgreSQL, mas a inferência do índice de expressão `coalesce(limiar_id,-1)` é
  frágil e diverge entre dialetos; rejeitado por não ser portável sem ginástica.
- Pré-SELECT "existe alerta ativo?" antes de inserir — rejeitado (reimplementa a chave fora do
  banco; TOCTOU se houvesse concorrência). Pode ser usado como *otimização* opcional para evitar
  churn de savepoints, mas a garantia autoritativa permanece o índice do banco.

---

## R5 — km confiável e detecção de inconsistência de hodômetro (FR-005, US4.2, ADR-002)

**Decisão**: o gatilho por **km** só é avaliável quando o km é confiável. Definição de km
confiável para um par (placa, tipo):
1. `veiculo.km_atual` presente e `> 0`; **e**
2. `ultima_manutencao.km_no_momento` presente (senão não há base para `km_desde`); **e**
3. `km_atual >= ultima.km_no_momento` (odômetro não pode ter "andado para trás").

Se qualquer condição falhar, o **km** daquele par é não-avaliável e vira impedimento →
`dados_insuficientes` (o gatilho por **tempo** do mesmo par ainda é avaliado normalmente, pois só
precisa da data).

**Evidência adicional (opcional, ADR-002)**: a série `abastecimento.km_hodometro` por placa pode
confirmar leituras decrescentes; na PoC isso entra apenas como texto no `detalhe` quando útil, não
como regra dura (constitution VII — simplicidade). A regra dura é `km_atual` × `km_no_momento`.

**Racional**: ADR-002 persistiu `km_hodometro` justamente porque odômetros inconsistentes existem;
a spec (edge case) manda tratar `km_atual < km_no_momento` como km não confiável → `dados_insuficientes`.
Manter a regra dura simples (dois escalares) evita varrer a série a cada verificação sem ganho de
sinal na PoC.

---

## R6 — Granularidade de `dados_insuficientes`: um por veículo, `detalhe` agrega (US4, SC-003)

**Decisão**: `dados_insuficientes` é **por veículo** (a chave `ux_alerta_ativo` colapsa em um por
placa, já que `limiar_id` é NULL). O motor coleta, por veículo, todos os **impedimentos** de
avaliação e, se houver ≥1, cria **um** alerta `dados_insuficientes` com `detalhe` enumerando as
causas (ex.: `"troca_oleo: sem manutenção registrada; revisao_geral: km não confiável (km_atual 100 < km_no_momento 500)"`).

Impedimentos que geram `dados_insuficientes`:
- Veículo cujo `tipo_veiculo` **não tem nenhuma** linha em `LIMIAR_CONFIG` → `detalhe: "sem limiar parametrizado para tipo_veiculo=X"` (edge case da spec).
- Par (placa, tipo avaliável) **sem última manutenção** registrada → impede km **e** tempo daquele tipo.
- Par com última manutenção mas **km não confiável** (R5) → impede só o km daquele tipo (o tempo ainda é avaliado).

Pares **sem linha** em `LIMIAR_CONFIG` para aquele `tipo_veiculo` **não** são impedimento (contrato
spec 002: par ausente = não-avaliável por definição, nunca default) — só contam para
`dados_insuficientes` quando o veículo não tem **nenhum** tipo avaliável.

**Racional**: alinha a regra à realidade do índice único (um `dados_insuficientes` ativo por placa)
e satisfaz SC-003 ("100% dos não-avaliáveis aparecem; zero silenciosamente ignorados"). O `detalhe`
carrega a rastreabilidade (constitution II) sem multiplicar linhas. Um veículo pode legitimamente
ter, ao mesmo tempo, um alerta `tempo` (tipo avaliável e vencido) **e** um `dados_insuficientes`
(outro tipo sem histórico) — são `tipo_gatilho` distintos, ambos ativos.

**Alternativas**:
- Um `dados_insuficientes` por (placa, tipo) — impossível sem mudar o esquema (a chave não inclui
  tipo quando `limiar_id` é NULL); rejeitado (mudaria contrato entregue da spec 002).
- Disparar `dados_insuficientes` só quando o veículo é **totalmente** inavaliável — rejeitado:
  deixaria gaps parciais silenciosos, violando III/SC-003.

---

## R7 — Resolução de alertas: motor é *create-only* (FR-004, Assumptions)

**Decisão**: o motor **nunca** apaga nem resolve alertas automaticamente. Ele só cria (ou faz
no-op). Resolver (`situacao='ativo' → 'resolvido'`) é ação manual (painel/script), conforme
Assumption da spec. Recorrência após resolução: como o índice único é parcial em `situacao='ativo'`,
um alerta `resolvido` **não** bloqueia a criação de um novo `ativo` quando a condição reaparece
(US3.3) — cai naturalmente do no-op sobre linhas ativas.

**Racional**: mantém o motor simples e idempotente (VII/VI); evita o motor "desfazer" uma
notificação que um gestor ainda não tratou. A edge case "limiar alterado com alerta ativo" é
coberta: o ativo não é tocado retroativamente; a próxima verificação usa o novo limiar e pode gerar
recorrência (novo par) — a "resolução conforme nova condição" fica a cargo da ação manual, não do
motor.

**Alternativas**: motor auto-resolve quando a condição deixa de valer — rejeitado nesta PoC
(complexidade + risco de apagar contexto antes do atendimento; fora do escopo declarado nas
Assumptions).

---

## R8 — Consulta "última manutenção por (placa, tipo)" (contrato spec 002)

**Decisão**: para cada (placa, tipo), obter a manutenção de maior `data` via `ORDER BY data DESC
LIMIT 1` (ou `row_number()`), apoiada no índice `ix_manutencao_placa_tipo_data (placa, tipo, data)`
que o contrato da spec 002 declara suportar exatamente esta consulta. Empate de mesma `data`: a
chave de unicidade `(placa, data, tipo)` garante no máximo uma linha por (placa, data, tipo), então
não há empate real por dia.

**Racional**: o índice já existe (spec 002) e é o caminho previsto; volume da PoC dispensa
otimização adicional.

---

## R9 — Intervalo do ciclo como env var (FR-006, SC-005, constitution V)

**Decisão**: variável `CICLO_INTERVALO_SEGUNDOS` (inteiro em segundos), lida por
`alertas/alert_config.py::intervalo_ciclo_segundos()`, **default 90** (1,5 min — dentro da faixa de demo
1–2 min da arquitetura §8). Documentar em `.env.example`. Segundos (não minutos) dá granularidade
para testes/ajuste fino sem tocar em código.

**Racional**: intervalo é parâmetro operacional → env var (constitution V; arquitetura §8);
o contrato da spec 003 diz explicitamente que "o intervalo do ciclo pertence ao agendador (spec
004)". Alterar o intervalo exige zero mudança de código (SC-005).

**Alternativas**: `CICLO_INTERVALO_MINUTOS` — menos flexível para teste; segundos é superconjunto.
Codificar 90s como constante — violaria a constituição V.

---

## Resumo das decisões

| # | Tema | Decisão |
|---|---|---|
| R1 | Agendador | APScheduler `BlockingScheduler`, 1 job ordenado (ETL→motor), `max_instances=1`, `coalesce=True` |
| R2 | Ponto de entrada | `verificar_alertas(hoje=None) -> dict` importável + CLI `python -m alertas.motor` |
| R3 | Relógio | `hoje` injetável, default `date.today()` |
| R4 | Idempotência | SAVEPOINT + `IntegrityError` no-op sobre `ux_alerta_ativo`; contagem por delta (dialeto-agnóstico) |
| R5 | km confiável | `km_atual>0` ∧ `km_no_momento` presente ∧ `km_atual ≥ km_no_momento`; senão impedimento |
| R6 | `dados_insuficientes` | 1 por veículo; `detalhe` agrega impedimentos; par sem limiar não é impedimento (só se veículo sem tipo avaliável) |
| R7 | Resolução | motor é create-only; resolução é manual; recorrência via índice parcial |
| R8 | Última manutenção | `ORDER BY data DESC LIMIT 1` sobre `ix_manutencao_placa_tipo_data` |
| R9 | Intervalo | `CICLO_INTERVALO_SEGUNDOS` (default 90), lido a cada start; sem constante no código |

Nenhum `NEEDS CLARIFICATION` remanescente.
