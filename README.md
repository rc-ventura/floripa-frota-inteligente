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

O trabalho está dividido em **7 especificações** (`specs/001` a `specs/007`), cada uma dizendo
**o que** construir e **por que** — o **como técnico** (stack, plano, tasks) fica a cargo de
quem assumir cada uma. Veja `specs/README.md` para o mapa completo, com dependências entre elas.

Documentos de referência, em ordem de desempate se houver conflito:

1. Briefing oficial do desafio (`.docx`, não editar)
2. `wiki/arquitetura_tecnica_desafio13_v2.md` — decisões técnicas (D1–D8), ERD, pipeline (v1 preservada; mudanças da v2 em `docs/decisoes/ADR-001..003`)
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

**Independentes (comecem já, em paralelo):**
- `001-fontes-dados-simuladas` — não depende de nenhuma outra spec.
- `002-modelo-dados-banco` — não depende de nenhuma outra spec.

Essas duas são o ponto de partida do projeto: dados (001) e schema/backend (002) são
frentes de pessoas diferentes que não se bloqueiam uma à outra.

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

**Sugestão de alocação com 4+ pessoas:** comecem `001` e `002` juntas no dia 1; assim que
`003` estiver pronto, uma pessoa ataca `004` (motor) enquanto outra já ataca `006` (custos)
em paralelo — só `005` precisa esperar `004` terminar.

---

## 3. O fluxo de trabalho (gitflow)

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

## 4. Como pegar uma spec

1. Abra `specs/README.md` e escolha uma spec ainda não assumida (veja a tabela de
   dependências — algumas só podem começar depois de outras estarem prontas).
2. Leia o `spec.md` da pasta escolhida: ele tem as histórias de usuário, requisitos
   testáveis e critérios de sucesso. É tudo que você precisa para começar a implementar.
3. Crie sua feature branch a partir de `dev` (seção 3).

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

## 5. Regras que não podem ser quebradas

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

## 6. Convenções de código

- Idioma: português no código de domínio (tabelas, campos, variáveis de negócio) e na
  documentação.
- Vocabulários padronizados em `snake_case` (ex.: `troca_oleo`); motivos de rejeição idem
  (`placa_invalida`, `data_ausente`, `duplicado`).
- Testes são critério de aceite do kanban (gatilhos do motor, idempotência da carga) —
  não deixe para depois.

---

## 7. Dúvidas

Se o `spec.md` da sua frente não responder, a ordem de consulta é: arquitetura técnica →
kanban original → constitution → perguntar no time. Se encontrar uma decisão de arquitetura
que precisa mudar, registre um ADR em `docs/decisoes/` e avise o grupo antes de seguir.
