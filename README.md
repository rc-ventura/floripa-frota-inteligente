# Floripa Frota Inteligente

PoC do **Desafio 13 — Gestão Inteligente da Frota Municipal** (1ª Jornada Incubintech),
para a Secretaria Municipal de Administração de Florianópolis.

**Critério de sucesso (binário):** frota unificada em painel único **+** alerta preventivo
disparado antes do vencimento, em demo ao vivo e reproduzível.

Este documento é o ponto de partida para quem entra na equipe agora. Para o contexto
completo do desafio, veja `wiki/wiki_desafio13_frota_municipal.md`.

---

## 1. Como o projeto está organizado

```
data/inbox/      pasta monitorada (conteúdo não versionado)   data/seeds/  datasets simulados
fake_api/        fonte simulada de multas                     pipeline/    extract/ transform/ load/
alertas/         motor de alertas                             db/          modelos + migrations
dashboard/       painéis (frota, alertas, custos)             tests/       testes automatizados
docs/decisoes/   ADRs                                         specs/       especificações (o que construir)
wiki/            briefing, arquitetura, kanban (fonte da verdade do desafio)
```

**Arquitetura em 4 camadas** — os componentes conversam só via banco; dashboard nunca lê
arquivo-fonte, motor nunca lê o pipeline diretamente (constitution VI):

![Arquitetura em 4 camadas](docs/checkpoints/img_hd/fluxo_hd.png)

O trabalho está dividido em **7 especificações** (`specs/001` a `specs/007`), cada uma dizendo
**o que** construir e **por que** — o **como técnico** (stack, plano, tasks) fica a cargo de
quem assumir cada uma. Veja `specs/README.md` para o mapa completo, com dependências entre elas.

Documentos de referência, em ordem de desempate se houver conflito:

1. Briefing oficial do desafio (`.docx`, não editar)
2. `wiki/arquitetura_tecnica_desafio13_v2.md` — decisões técnicas (D1–D8), ERD, pipeline (v1 preservada; mudanças da v2 em `docs/decisoes/ADR-001..004`)
3. `specs/*/spec.md` — o que cada parte precisa entregar
4. `wiki/kanban_tasks_desafio13_frota_municipal.md` — as 36 tasks originais, por fase
5. `.specify/memory/constitution.md` — princípios inegociáveis do projeto

---

## 2. Sequência das specs — o que é paralelo e o que é dependente

```
001-fontes-dados-simuladas ─┐
                             ├─► 003-pipeline-etl ─► 004-motor-alertas ─► 005-painel-frota-alertas ─┐
002-modelo-dados-banco ─────┘             │                                                          ├─► 007-demo-empacotamento-conformidade
                                           └───────────────────────────► 006-painel-custos ──────────┘
```

**ERD** — 8 entidades consolidadas, placa canônica (ADR-001) como chave de reconciliação
entre as 4 fontes. Diagrama completo (12 tabelas com staging + `log_qualidade`) em
`specs/002-modelo-dados-banco/data-model.md`:

![ERD — 8 tabelas consolidadas](docs/checkpoints/img_hd/erd_hd.png)

**Estado atual (2026-07-17):**

| Spec | Status |
|---|---|
| `001-fontes-dados-simuladas` | ✅ entregue em `dev` (PRs #2 e #3) |
| `002-modelo-dados-banco` | ✅ entregue em `dev` (PR #4) |
| `003-pipeline-etl` | 🔓 desbloqueada — é a próxima do caminho crítico |
| `004` a `007` | ⏳ aguardando dependências (tabela abaixo) |

As duas specs independentes (dados e schema) já foram entregues — o que existe de
concreto delas, e como rodar, está na seção 3.

**Dependentes:**

| Spec | Depende de | Por quê |
|---|---|---|
| `003-pipeline-etl` | 001 + 002 | precisa dos dados simulados (para extrair) **e** do schema (para carregar) |
| `004-motor-alertas` | 002 + 003 | lê `LIMIAR_CONFIG`/`ALERTA` (002) e os dados consolidados que o pipeline carrega (003) |
| `005-painel-frota-alertas` | 002 + 003 + 004 | exibe dados consolidados (003) e alertas (004) |
| `006-painel-custos` | 002 + 003 | só precisa dos gastos consolidados — **não depende de 004** |
| `007-demo-empacotamento-conformidade` | todas (001–006) | empacota e ensaia o sistema completo |

**Caminho crítico da demo** (bloqueia o disparo do alerta ao vivo — tasks 🔴 do kanban):

```
001 + 002 ──► 003 ──► 004 ──► 005 ──► 007
```

**Ramo paralelo ao caminho crítico:** `006` só depende de `003`, não de `004`/`005` — quem
pegar o painel de custos pode trabalhar em paralelo com quem estiver no motor de alertas ou
no painel de frota, assim que o pipeline (003) estiver de pé.

**Sugestão de alocação:** com `001` e `002` entregues, o foco vai todo para `003`; assim
que ela estiver pronta, uma pessoa ataca `004` (motor) enquanto outra já ataca `006`
(custos) em paralelo — só `005` precisa esperar `004` terminar.

---

## 3. Roadmap

Progresso das 36 tasks do kanban original (`wiki/kanban_tasks_desafio13_frota_municipal.md`),
atualizado conforme cada spec é entregue. **Legenda:** 🔴 `demo-crítico` · 🟡 `compliance`
(LGPD/LAI/Lei 14.133).

### Fase 0 — Modelagem (5 tasks)

- [ ] 1. Definir papéis da equipe — tabela de papéis registrada no repositório
- [x] 2. Decidir dados reais vs simulados — dados simulados formalizados (spec 001)
- [x] 3. Validar modelo de dados unificado — ERD v2 materializado em 12 tabelas (spec 002)
- [x] 4. 🔴 Definir limiares iniciais (LIMIAR_CONFIG) — 9 linhas semeadas de `limiares_semente.json` (spec 002)
- [x] 5. 🟡 Mapear campos com dado pessoal — introspecção LGPD no esquema, zero de-para (spec 002 US3)

### Fase 1 — Integração de dados (10 tasks)

- [x] 1. 🔴 Criar gerador_dados.py (4 fontes) — `data/gerador_dados.py` + 4 datasets com inconsistências (spec 001)
- [x] 2. Subir API fake de multas (FastAPI) — `fake_api/main.py` servindo multas (spec 001)
- [x] 3. Modelar banco (SQLAlchemy + migrations) — `db/models.py` + 2 migrations + `init_db.py` idempotente (spec 002)
- [ ] 4. 🔴 Extrator de abastecimento (CSV/pasta monitorada) — spec 003
- [ ] 5. Extrator de multas (API) — spec 003
- [ ] 6. Extrator de manutenção (XLSX) — spec 003
- [ ] 7. Extrator de licenciamento (SQLite) — spec 003
- [ ] 8. 🔴 Transformação e regras de qualidade — spec 003
- [ ] 9. 🔴 Carga idempotente (upsert) — chaves UNIQUE prontas no banco (spec 002/ADR-004); carga é spec 003
- [ ] 10. Documentar pipeline e rastreabilidade — spec 003

### Fase 2 — Motor de alertas (6 tasks) — spec 004

- [ ] 1. 🔴 Alerta por quilometragem
- [ ] 2. 🔴 Alerta por tempo
- [ ] 3. Idempotência e histórico de alertas
- [ ] 4. Alerta dados_insuficientes
- [ ] 5. 🔴 Cenário determinístico da demo
- [ ] 6. 🔴 Agendamento (APScheduler)

### Fase 3 — Painel da frota (6 tasks) — spec 005

- [ ] 1. 🔴 Visão situação da frota
- [ ] 2. Drill-down por veículo
- [ ] 3. 🔴 Visão de alertas
- [ ] 4. 🟡 Toggle Gestor/Pública
- [ ] 5. 🔴 Auto-refresh do painel
- [ ] 6. Teste de usabilidade externo

### Fase 3a — Painel de custos (3 tasks) — spec 006

- [ ] 1. Consolidação de gastos
- [ ] 2. Comparativo entre veículos
- [ ] 3. Marcar indicadores derivados vs calculados

### Fase 4 — Demo e conformidade (6 tasks) — spec 007

- [ ] 1. Análise de impacto econômico
- [ ] 2. 🟡 Documento de conformidade LGPD/LAI/14.133
- [ ] 3. 🔴 Docker Compose funcional
- [ ] 4. 🔴 Ensaio da demo ao vivo
- [ ] 5. 🔴 Vídeo plano B do disparo do alerta
- [ ] 6. Pitch e posicionamento

**Progresso:** 7/36 tasks concluídas — Fase 0: 4/5 · Fase 1: 3/10 · Fases 2–4: 0/21

> Próxima do caminho crítico: **spec 003 (pipeline ETL)** — desbloqueada, é o pré-requisito
> do motor de alertas (004) e dos painéis (005/006).

---

## 4. O que já está pronto e como rodar

Pré-requisitos: **Python 3.12+** e **[uv](https://docs.astral.sh/uv/)**. `uv sync` instala
tudo (SQLAlchemy, Alembic, psycopg, FastAPI, pytest…). Os comandos abaixo usam `uv run`;
com o venv ativo (`source .venv/bin/activate`), o prefixo é dispensável.

### Fontes simuladas (spec 001)

- `data/seeds/` — datasets das 4 fontes legadas (CSV, XLSX, JSON e SQLite), com
  inconsistências propositais documentadas em `data/seeds/INCONSISTENCIAS.md`.
  Para regenerar: `uv run python data/gerador_dados.py`.
- `fake_api/` — API FastAPI que serve as multas:
  `uv run uvicorn fake_api.main:app --port 8000` (endpoints em `fake_api/README.md`).

![Evidência: endpoint /multas, datasets e testes](docs/checkpoints/img/evidencia_combinada.png)

*Endpoint `/multas` retornando JSON (placas em minúsculas, CNH sintética — LGPD), datasets
das 4 fontes em `data/seeds/`, 10 testes automatizados passando.*

### Banco consolidado (spec 002)

```bash
uv run python -m db.init_db
```

Um comando, idempotente (pode rodar N vezes): aplica as migrations Alembic até `head` e
semeia `limiar_config` a partir de `data/seeds/limiares_semente.json` — upsert que
**preserva edições feitas ao vivo** no banco; para adotar novos valores do JSON num banco
existente, `uv run python -m db.seed_limiares --sobrescrever`.

- **Banco default**: SQLite em `db/frota.db`. Para Postgres, aponte `DATABASE_URL`
  (ex.: `postgresql+psycopg://user:senha@localhost:5432/frota`) — mesmo esquema, zero
  mudança de código (decisão D2).
- **Testes**: `uv run pytest tests/test_db.py` — criação do zero, idempotência dupla,
  seed espelha o JSON, chaves de upsert (positivo e negativo, ADR-004), introspecção LGPD.
- **Roteiro completo de validação**: `specs/002-modelo-dados-banco/quickstart.md`.

**Diagramas ER** (12 tabelas: 7 consolidadas + 4 staging + `log_qualidade`):

![ER consolidadas](docs/modelagem/v1/diagrama_er_consolidadas.png)

*Consolidadas e relacionamentos — placa canônica como PK de `veiculo` e FK dos eventos.*

![ER staging](docs/modelagem/v1/diagrama_er_staging.png)

*Staging (`stg_*`, uma por fonte, tipos frouxos) + `log_qualidade` — sem FKs por design.*

---

## 5. O fluxo de trabalho (gitflow)

- `main` e `dev` são branches **permanentes** e **protegidas**: ninguém dá push direto nelas,
  force-push é bloqueado, e todo merge exige um Pull Request com **pelo menos 1 aprovação**.
- Toda feature nasce de `dev`, nunca de `main`.
- `main` só recebe merge de `dev` em ponto de release/demo.

Passo a passo para qualquer tarefa:

```bash
git checkout dev
git pull
git checkout -b feature/00X-nome-da-spec   # nome = cabeçalho da spec que você pegou
# ... trabalhar, commitar ...
git push -u origin feature/00X-nome-da-spec
# abrir PR no GitHub apontando para dev
```

**Commits e PRs em português**, mensagem no imperativo com prefixo convencional:
`feat:`, `fix:`, `chore:`, `docs:`, `test:`.

---

## 6. Como pegar uma spec

1. Abra `specs/README.md` e escolha uma spec ainda não assumida (veja a tabela de
   dependências — algumas só podem começar depois de outras estarem prontas).
2. Leia o `spec.md` da pasta escolhida: ele tem as histórias de usuário, requisitos
   testáveis e critérios de sucesso. É tudo que você precisa para começar a implementar.
3. Crie sua feature branch a partir de `dev` (seção 4).

A partir daqui, escolha o caminho que preferir — **os dois são igualmente válidos** e levam
ao mesmo lugar (código + PR para `dev`):

### Caminho A — com Speckit (se quiser plano técnico e tasks gerados)

Este repositório já vem com os slash commands do Speckit (`.claude/skills/speckit-*`) e o
esqueleto em `.specify/`. Se você usa Claude Code (ou outro agente com suporte a Speckit):

```bash
# aponte o Speckit para a sua spec
echo '{ "feature_directory": "specs/00X-nome-da-spec" }' > .specify/feature.json
```

Depois rode, na ordem: `/speckit-clarify` (opcional, se houver dúvida) → `/speckit-plan`
(gera `plan.md` com o design técnico) → `/speckit-tasks` (gera `tasks.md` com o passo a
passo) → implemente (manualmente ou com `/speckit-implement`). Tudo nasce dentro da pasta
da própria spec, sem afetar quem está usando o Caminho B.

### Caminho B — sem Speckit (direto ao código)

Não precisa de nenhuma ferramenta especial. Leia o `spec.md`, decida a stack e a estrutura
de pastas dentro da sua área (respeitando as decisões D1–D8 da arquitetura), e implemente
diretamente. Use o `spec.md` como checklist de aceite antes de abrir o PR.

Nenhum dos dois caminhos é obrigatório — misturar também é normal (ex.: uma pessoa gera
`plan.md` com Speckit e o resto do time só lê e implementa a partir dele).

---

## 7. Regras que não podem ser quebradas

Resumo da constitution (`.specify/memory/constitution.md`) — leia o documento completo antes
de tomar decisões de modelagem ou de escopo:

- **Placa canônica** (maiúsculas, sem hífen; formatos antigo `AAA9999` **e** Mercosul
  `AAA9A99` — regex `^[A-Z]{3}\d[A-Z\d]\d{2}$`, ADR-001) é a chave de reconciliação entre
  todas as fontes; normalize antes de qualquer cruzamento.
- **Rastreabilidade**: toda tabela consolidada carrega `fonte_origem`; staging carrega
  carimbo de carga; nenhuma rejeição é silenciosa — vai para `log_qualidade` com motivo.
- **LGPD**: nenhum dado pessoal real, nunca. Condutor existe só como `condutor_pseudo`
  (`COND-NNN`); não existe tabela de-para na PoC. Visão pública mostra só agregados.
- **Parametrização como dados**: limiares vivem em `LIMIAR_CONFIG` (tabela), intervalo do
  ciclo em variável de ambiente. Constante de negócio no código é violação.
- **Camadas conversam só via banco**: dashboard nunca lê arquivo-fonte; motor nunca lê o
  pipeline diretamente.
- **Idempotência**: pipeline, motor e migrations podem rodar N vezes → mesmo estado final.
- **Demo-crítico primeiro**: entre duas tarefas, priorize a que participa do disparo do
  alerta ao vivo (marcadas 🔴 no kanban).

---

## 8. Convenções de código

- Idioma: português no código de domínio (tabelas, campos, variáveis de negócio) e na
  documentação.
- Vocabulários padronizados em `snake_case` (ex.: `troca_oleo`); motivos de rejeição idem
  (`placa_invalida`, `data_ausente`, `duplicado`).
- Testes são critério de aceite do kanban (gatilhos do motor, idempotência da carga) —
  não deixe para depois.

---

## 9. Dúvidas

Se o `spec.md` da sua frente não responder, a ordem de consulta é: arquitetura técnica →
kanban original → constitution → perguntar no time. Se encontrar uma decisão de arquitetura
que precisa mudar, registre um ADR em `docs/decisoes/` e avise o grupo antes de seguir.
