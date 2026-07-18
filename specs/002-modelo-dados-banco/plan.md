# Implementation Plan: Modelo de Dados e Banco Consolidado

**Branch**: `feature/002-modelo-dados-banco` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-modelo-dados-banco/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Materializar o ERD da arquitetura v2 (§4) como esquema relacional versionado: 7 entidades
consolidadas (VEICULO, ABASTECIMENTO com `km_hodometro`, MANUTENCAO com `categoria`, MULTA,
LICENCIAMENTO, LIMIAR_CONFIG, ALERTA) + 4 tabelas de staging (`stg_*`, uma por fonte, tipos
frouxos) + `log_qualidade` (12 tabelas no total). Implementação com SQLAlchemy 2.x + Alembic (decisão D2: começa em
SQLite local e troca para PostgreSQL 16 da demo só pela `DATABASE_URL`, sem reescrever código).
Criação do esquema + seed da `LIMIAR_CONFIG` em **um comando idempotente** (`python -m db.init_db`);
o seed lê `data/seeds/limiares_semente.json` diretamente (fonte única — elimina a duplicação
por convenção com a spec 001). Placa canônica nos dois formatos (ADR-001), rastreabilidade
(`fonte_origem` + `carga_em`) e LGPD (só `condutor_pseudo`, zero estrutura de de-para) embutidas
no modelo. É o contrato de dados que destrava as specs 003 (pipeline), 004 (motor) e 005/006 (painéis).

## Technical Context

**Language/Version**: Python 3.12+ (decisão D1; ambiente atual 3.13).

**Primary Dependencies**:
- `sqlalchemy>=2.0` — modelos declarativos 2.x, engine única para SQLite/PostgreSQL (D2).
- `alembic>=1.13` — migrations versionadas e re-executáveis (FR-007).
- `psycopg[binary]>=3.1` — driver PostgreSQL para o ambiente da demo (D2/D6).
- Reusa `pytest` (já no dev-group) para os testes de aceitação.

**Storage**: dois ambientes, mesmo esquema (SC-001, edge case "troca de banco"):
- Local/dev: SQLite (`sqlite:///db/frota.db` — default quando `DATABASE_URL` ausente).
- Demo: PostgreSQL 16 via Docker Compose (spec 007), selecionado por `DATABASE_URL`.

**Testing**: `pytest` em `tests/test_db.py` — criação do zero, re-execução idempotente (SC-004),
seed espelhando o JSON, edição de limiar em runtime sem restart (SC-002), rejeição de placa
inválida, introspecção LGPD (nenhuma tabela liga pseudônimo a identidade — SC-003).

**Target Platform**: local (dev) e container da demo (D6). Sem serviços externos.

**Project Type**: biblioteca interna (`db/`) + CLI de inicialização (`python -m db.init_db`).

**Performance Goals**: criação completa do esquema + seed em < 1 min nos dois ambientes (SC-001).
Volume da PoC é trivial (40 veículos, ~2.000 eventos) — sem necessidade de tuning.

**Constraints**:
- Idempotência: criar o esquema N vezes → mesmo estado, sem erro nem perda de dados (SC-004, constitution VI).
- Placa canônica dual `AAA9999`/`AAA9A99` validada por regex única compartilhada (ADR-001).
- `km_hodometro` no ABASTECIMENTO (ADR-002) e `categoria` na MANUTENCAO (ADR-003 item 7).
- `fonte_origem` em toda consolidada; `carga_em` + origem em todo staging (constitution II).
- Zero estrutura de-para condutor→identidade (constitution IV; FR-006).
- Staging com tipos frouxos (TEXT): qualidade é imposta na transformação (spec 003), não na entrada (assumption da spec).
- Limiar é dado: `LIMIAR_CONFIG` editável em runtime, sem cache no processo (SC-002, constitution V).

**Scale/Scope**: PoC — 12 tabelas + ~10 índices/constraints; 9 linhas de seed; sem particionamento/retention automatizado (expurgo documentado via `carga_em`, arquitetura §10).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Avaliação contra a constitution v1.0.1 (`.specify/memory/constitution.md`):

| Princípio | Status | Evidência / Nota |
|---|---|---|
| **I. Demo-crítico primeiro** | ✅ PASS | Spec marcada 🔴 (task 4 da Fase 0): `LIMIAR_CONFIG` editável ao vivo é momento planejado da demo (US2/SC-002). O esquema é pré-requisito de todo o caminho crítico 003→004→005. |
| **II. Rastreabilidade total** | ✅ PASS | `fonte_origem` em TODAS as consolidadas (incluindo VEICULO — ver nota no data-model); `carga_em` + identificação de arquivo/endpoint em todo `stg_*`; `log_qualidade` com registro bruto + motivo (FR-002/FR-003). |
| **III. Dado inconsistente é requisito** | ✅ PASS | Staging aceita bruto sujo (tudo TEXT, sem constraints rígidas); constraints de qualidade vivem só nas consolidadas — a fronteira é exatamente o Validate & Transform da spec 003. |
| **IV. Conformidade (LGPD)** | ✅ PASS | Condutor existe apenas como `condutor_pseudo`; nenhuma tabela/coluna de-para no esquema (testado por introspecção). Nota: staging de multas carrega `cnh` sintética como dado bruto (rastreabilidade); descarte na consolidação é da spec 003; retenção via `carga_em` documentada. |
| **V. Parametrização como dados** | ✅ PASS | `LIMIAR_CONFIG` é tabela, semeada de `data/seeds/limiares_semente.json` (fonte única versionada — melhora sobre a sincronização "por convenção" registrada no Complexity Tracking da spec 001). `DATABASE_URL` por variável de ambiente. Zero constante de negócio no código do banco. |
| **VI. Camadas isoladas, idempotência** | ✅ PASS | Este módulo só define esquema/seed — não lê fontes nem implementa regra de motor. `alembic upgrade head` + seed com upsert são re-executáveis (SC-004). |
| **VII. Simplicidade, open source** | ✅ PASS | SQLAlchemy + Alembic são o par padrão do ecossistema (D1/D2), open source, sem lock-in; SQLite↔Postgres cobre local e demo sem infraestrutura extra. |

**Gate result: PASS.** Nenhuma violação; sem itens para Complexity Tracking.

**Re-check pós-Phase 1: PASS** — o design (data-model.md, contracts/) não introduziu violação;
a única adição fora do ERD literal é `fonte_origem` em VEICULO + `detalhe` em ALERTA, ambas
derivadas de exigências da constitution/spec 004 e documentadas no data-model.

## Project Structure

### Documentation (this feature)

```text
specs/002-modelo-dados-banco/
├── spec.md              # Especificação (já existia; atualizada pelos ADRs 001–003)
├── plan.md              # Este arquivo (/speckit-plan)
├── research.md          # Phase 0: decisões técnicas R1–R8 (/speckit-plan)
├── data-model.md        # Phase 1: esquema completo — 12 tabelas, constraints, índices (/speckit-plan)
├── quickstart.md        # Phase 1: guia de validação executável (/speckit-plan)
├── contracts/
│   └── esquema_tabelas.md   # Contrato do esquema consumido pelas specs 003/004/005/006 + contrato do comando de init
└── tasks.md             # Phase 2 (/speckit-tasks — NÃO criado por /speckit-plan)
```

### Source Code (repository root)

Aderente à arquitetura v2 §9 (`db/` já existe com `migrations/` vazio). Apenas arquivos desta spec:

```text
db/
├── __init__.py
├── config.py            # resolve DATABASE_URL (env var; default sqlite:///db/frota.db)
├── models.py            # SQLAlchemy 2.x: 7 consolidadas + 4 staging + log_qualidade
├── seed_limiares.py     # upsert da LIMIAR_CONFIG a partir de data/seeds/limiares_semente.json
├── init_db.py           # ponto de entrada único: alembic upgrade head + seed (idempotente)
└── migrations/          # Alembic: alembic.ini (na raiz de db/), env.py, versions/0001_esquema_inicial.py

tests/
└── test_db.py           # aceitação: criação, idempotência, seed, runtime-edit, placa, LGPD

.env.example              # DATABASE_URL comentada (previsto na arquitetura §9; criado aqui se ausente)
pyproject.toml            # + sqlalchemy, alembic, psycopg[binary]
```

**Structure Decision**: biblioteca única em `db/` (papel ⚙️ Backend), consumida pelas demais
camadas exclusivamente via banco (constitution VI). O Alembic vive dentro de `db/migrations/`
com `env.py` importando `db.models.Base.metadata`, para migrations e modelos nunca divergirem.
Testes na suíte única `tests/` do repositório, padrão estabelecido pela spec 001.

## Complexity Tracking

> Nenhuma violação da constitution — tabela não aplicável. (A duplicação de limiares apontada
> no Complexity Tracking da spec 001 é **resolvida** aqui: o seed passa a ler o próprio
> `limiares_semente.json`, eliminando a segunda cópia literal dos valores.)
