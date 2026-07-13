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
2. `wiki/arquitetura_tecnica_desafio13_v1.md` — decisões técnicas (D1–D8), ERD, pipeline
3. `specs/*/spec.md` — o que cada parte precisa entregar
4. `wiki/kanban_tasks_desafio13_frota_municipal.md` — as 36 tasks originais, por fase
5. `.specify/memory/constitution.md` — princípios inegociáveis do projeto

---

## 2. O fluxo de trabalho (gitflow)

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

## 3. Como pegar uma spec

1. Abra `specs/README.md` e escolha uma spec ainda não assumida (veja a tabela de
   dependências — algumas só podem começar depois de outras estarem prontas).
2. Leia o `spec.md` da pasta escolhida: ele tem as histórias de usuário, requisitos
   testáveis e critérios de sucesso. É tudo que você precisa para começar a implementar.
3. Crie sua feature branch a partir de `dev` (seção 2).

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

## 4. Regras que não podem ser quebradas

Resumo da constitution (`.specify/memory/constitution.md`) — leia o documento completo antes
de tomar decisões de modelagem ou de escopo:

- **Placa canônica `AAA9999`** (maiúsculas, sem hífen) é a chave de reconciliação entre
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

## 5. Convenções de código

- Idioma: português no código de domínio (tabelas, campos, variáveis de negócio) e na
  documentação.
- Vocabulários padronizados em `snake_case` (ex.: `troca_oleo`); motivos de rejeição idem
  (`placa_invalida`, `data_ausente`, `duplicado`).
- Testes são critério de aceite do kanban (gatilhos do motor, idempotência da carga) —
  não deixe para depois.

---

## 6. Dúvidas

Se o `spec.md` da sua frente não responder, a ordem de consulta é: arquitetura técnica →
kanban original → constitution → perguntar no time. Se encontrar uma decisão de arquitetura
que precisa mudar, registre um ADR em `docs/decisoes/` e avise o grupo antes de seguir.
