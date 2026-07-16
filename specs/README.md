# Especificações — Desafio 13: Gestão Inteligente da Frota Municipal

Este diretório é o esqueleto de especificações do projeto. **Cada pasta contém apenas um `spec.md`**: ele diz *o que* construir e *por quê*. O *como* (plano técnico e tasks) é gerado por quem assumir a spec, usando o fluxo Speckit descrito abaixo.

Documentos de referência: `wiki/arquitetura_tecnica_desafio13_v2.md` (decisões técnicas — vigente; mudanças da v2 em `docs/decisoes/ADR-001..003`), `wiki/kanban_tasks_desafio13_frota_municipal.md` (36 tasks por fase) e `.specify/memory/constitution.md` (princípios inegociáveis do projeto, derivados dos critérios de aceite do briefing — todo plano passa pelo gate "Constitution Check").

## Mapa de specs

| Spec | Entrega | Papel principal | Fases do kanban | Depende de |
|---|---|---|---|---|
| `001-fontes-dados-simuladas` | 4 datasets com inconsistências propositais + API fake de multas + cenário determinístico da demo | 🗂️ Dados (+ ⚙️ Backend) | F0 t2 · F1 t1–t2 · F2 t5 | — |
| `002-modelo-dados-banco` | Esquema completo (staging, consolidadas, LIMIAR_CONFIG, ALERTA, log_qualidade) + limiares iniciais | ⚙️ Backend | F0 t3–t4 · F1 t3 | — |
| `003-pipeline-etl` | Extract → Validate & Transform → Load das 4 fontes, log de qualidade, carga idempotente | 🗂️ Dados (+ ⚙️ Backend) | F1 t4–t10 | 001, 002 |
| `004-motor-alertas` | Alertas por km/tempo, idempotência, histórico, `dados_insuficientes`, ciclo agendado | ⚙️ Backend | F2 t1–t4, t6 | 002, 003 |
| `005-painel-frota-alertas` | Semáforo da frota, visão de alertas, drill-down, toggle Gestor/Pública, auto-refresh | 🖥️ Frontend | F3 t1–t6 | 002, 003, 004 |
| `006-painel-custos` | Gastos por veículo/período/tipo, comparativo (candidato a renovação), indicadores marcados, export CSV | 🖥️ Frontend | F3a t1–t3 | 002, 003 |
| `007-demo-empacotamento-conformidade` | Subida em 1 comando, doc LGPD/LAI/14.133, impacto econômico, roteiro de demo + vídeo plano B | ⚙️+📄+👥 | F0 t5 · F4 t1–t6 | todas |

> A task 1 da Fase 0 (definir papéis da equipe) é organizacional e não vira spec: registre a tabela de papéis neste repositório (ex.: `docs/papeis.md`).

### Ordem de trabalho

```
001 (dados)  ──┐
               ├──► 003 (pipeline) ──► 004 (motor) ──► 005 (painel frota/alertas) ──┐
002 (banco)  ──┘                              └──────► 006 (painel custos) ────────┼──► 007 (demo)
```

001 e 002 andam em paralelo desde já. 005 pode começar com dados consolidados (003) usando alertas inseridos à mão até 004 ficar pronta.

## Fluxo de trabalho Git (gitflow)

- Branches permanentes: `main` (estável/apresentação) e `dev` (integração).
- Cada spec vira uma feature branch com o nome indicado no cabeçalho dela (ex.: `feature/003-pipeline-etl`). Se a spec for grande, quebre em branches menores prefixadas igual (ex.: `feature/003-pipeline-etl-extratores`).
- **Todo MR/PR aponta para `dev`**, nunca direto para `main`. `dev` → `main` somente em ponto de release/demo.
- Pelo menos 1 revisão de outro membro antes do merge.

## Como assumir uma spec (fluxo Speckit)

1. Crie sua branch a partir de `dev` com o nome do cabeçalho da spec.
2. Aponte o Speckit para a sua spec editando `.specify/feature.json`:
   ```json
   { "feature_directory": "specs/00X-nome-da-spec" }
   ```
3. Leia o `spec.md` e valide dúvidas com o time (ou rode `/speckit-clarify`).
4. Rode `/speckit-plan` para gerar o plano técnico e depois `/speckit-tasks` para as tasks — esses artefatos nascem dentro da pasta da sua spec.
5. Implemente (`/speckit-implement` ou manualmente), abra MR para `dev` e vincule as tasks do kanban correspondentes.

**Convenção**: não edite a spec de outra pessoa sem combinar; mudanças de escopo passam pelo time (e, se mudarem decisão de arquitetura, incrementam a versão do documento em `wiki/`).
