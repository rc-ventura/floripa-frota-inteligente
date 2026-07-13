# Desafio 13 — Gestão Inteligente da Frota Municipal (Florianópolis)

PoC de hackathon (1ª Jornada Incubintech): integrar 4 fontes legadas de dados da frota
municipal em um painel único com motor de alertas de manutenção preventiva.

**Critério de sucesso (binário):** frota unificada em painel único **+** alerta preventivo
disparado antes do vencimento, em demo ao vivo e reproduzível.

## Documentos-fonte (ordem de desempate)

1. `Desafio13_briefingFrotaMunicipal.docx` — briefing oficial (não editar)
2. `wiki/arquitetura_tecnica_desafio13_v1.md` — decisões técnicas D1–D8, ERD, pipeline, stack
3. `specs/` — 7 especificações (ver `specs/README.md` para o mapa e dependências)
4. `wiki/kanban_tasks_desafio13_frota_municipal.md` — 36 tasks por fase
5. `.specify/memory/constitution.md` — princípios inegociáveis (resumo abaixo)

## Fluxo de trabalho

- **Speckit**: cada pasta em `specs/` contém apenas `spec.md` até alguém assumi-la. Para
  trabalhar numa spec: aponte `.specify/feature.json` para ela, rode `/speckit-plan` e
  `/speckit-tasks` (os artefatos nascem na pasta da spec), depois implemente.
- **Gitflow**: `main` (estável/demo) e `dev` (integração) são permanentes. Feature branches
  saem de `dev` com o nome do cabeçalho da spec (ex.: `feature/003-pipeline-etl`). Todo
  MR aponta para `dev` com ≥1 revisão; `dev` → `main` só em release/demo.
- Commits e MRs em português, mensagem no imperativo com prefixo convencional
  (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).

## Regras inegociáveis (constitution v1.0.0 — ler antes de codar)

- **Demo-crítico primeiro**: priorize sempre o caminho do disparo do alerta ao vivo.
- **Placa canônica `AAA9999`** (maiúsculas, sem hífen) é a chave de reconciliação; normalize
  antes de qualquer cruzamento.
- **Rastreabilidade**: toda tabela consolidada carrega `fonte_origem`; staging carrega
  carimbo de carga; rejeição nunca é silenciosa — vai para `log_qualidade` com motivo.
- **LGPD**: nenhum dado pessoal real, nunca. Condutor existe apenas como `condutor_pseudo`
  (`COND-NNN`); não existe tabela de-para na PoC. Visão pública exibe só agregados.
- **Parametrização como dados**: limiares vivem em `LIMIAR_CONFIG` (tabela), intervalo do
  ciclo em variável de ambiente. Constante de negócio no código é violação.
- **Camadas conversam só via banco**: dashboard nunca lê arquivo-fonte; motor nunca lê o
  pipeline.
- **Idempotência**: pipeline, motor e migrations podem rodar N vezes → mesmo estado.
- **Simplicidade > sofisticação**; tudo open source, sem lock-in.

## Estrutura do repositório

```
data/inbox/      pasta monitorada (conteúdo não versionado)   data/seeds/  datasets simulados
fake_api/        fonte simulada de multas                     pipeline/    extract/ transform/ load/
alertas/         motor de alertas                             db/          modelos + migrations
dashboard/       painéis (frota, alertas, custos)             tests/       testes automatizados
docs/decisoes/   ADRs                                         specs/       especificações speckit
```

## Convenções de código

- Idioma: português no código de domínio (tabelas, campos, variáveis de negócio) e docs.
- Stack: seguir as decisões D1–D8 da arquitetura; mudança de decisão exige nova versão do
  documento de arquitetura + ADR em `docs/decisoes/`.
- Testes são critério de aceite do kanban (gatilhos do motor, idempotência da carga) — não
  deixe para depois.
- Vocabulários padronizados em snake_case (ex.: `troca_oleo`); motivos de rejeição idem
  (`placa_invalida`, `data_ausente`, `duplicado`).
