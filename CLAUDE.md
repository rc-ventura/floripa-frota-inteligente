# Desafio 13 — Gestão Inteligente da Frota Municipal (Florianópolis)

PoC de hackathon (1ª Jornada Incubintech): integrar 4 fontes legadas de dados da frota
municipal em um painel único com motor de alertas de manutenção preventiva.

**Critério de sucesso (binário):** frota unificada em painel único **+** alerta preventivo
disparado antes do vencimento, em demo ao vivo e reproduzível.

## Documentos-fonte (ordem de desempate)

1. `Desafio13_briefingFrotaMunicipal.docx` — briefing oficial (não editar)
2. `wiki/arquitetura_tecnica_desafio13_v2.md` — decisões técnicas D1–D8, ERD, pipeline, stack (v1 preservada; mudanças da v2 nos ADRs 001–002)
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
- **Placa canônica** (maiúsculas, sem hífen; formatos antigo `AAA9999` **e** Mercosul
  `AAA9A99` — regex `^[A-Z]{3}\d[A-Z\d]\d{2}$`, ADR-001) é a chave de reconciliação;
  normalize antes de qualquer cruzamento.
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

## ADRs — Decisões técnicas

> Pasta: `./docs/decisoes/`

| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [ADR-001](./docs/decisoes/ADR-001-placa-canonica-dois-formatos.md) | Placa canônica aceita os dois formatos brasileiros (antigo + Mercosul) | Proposta | 2026-07-14 |
| [ADR-002](./docs/decisoes/ADR-002-persistir-km-hodometro-abastecimento.md) | Persistir o km do hodômetro na tabela consolidada `ABASTECIMENTO` | Proposta | 2026-07-14 |
| [ADR-003](./docs/decisoes/ADR-003-calibracao-realismo-fontes-simuladas.md) | Calibração de realismo das fontes simuladas (gerador — spec 001) | Proposta | 2026-07-14 |
| [ADR-004](./docs/decisoes/ADR-004-null-em-chaves-de-upsert.md) | Tratamento de NULL em chaves de unicidade/upsert das consolidadas (coalesce-sentinela) | Proposta | 2026-07-17 |
| [ADR-005](./docs/decisoes/ADR-005-sobrescrita-upsert-dimensoes.md) | Política de sobrescrita/merge no upsert de dimensões (`on_conflict_do_update`) | Proposta | 2026-07-20 |
| [ADR-006](./docs/decisoes/ADR-006-idempotencia-motor-insert-lote-on-conflict.md) | Idempotência do motor por INSERT em lote com `ON CONFLICT DO NOTHING` + delta de `COUNT` (spec 004) | Proposta | 2026-07-20 |

## Learning Lessons

> Pasta: `./docs/learning-lessons/`

- [Proteja a âncora do ruído: teste o invariante negativo em geradores de dados](./docs/learning-lessons/proteja_a_ancora_do_ruido_e_teste_o_invariante_negativo.md) — 2026-07-15
- [Valide o ciclo de ponta a ponta nos dois bancos-alvo](./docs/learning-lessons/valide_o_ciclo_de_ponta_a_ponta_nos_dois_bancos_alvo.md) — 2026-07-19
