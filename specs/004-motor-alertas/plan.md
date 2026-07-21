# Implementation Plan: Motor de Alertas Preventivos e Agendamento

**Branch**: `feature/004-motor-alertas` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-motor-alertas/spec.md`

## Summary

Motor de manutenção preventiva que, a cada ciclo, lê o estado consolidado (spec 003) e a
parametrização de `LIMIAR_CONFIG` (spec 002) e grava alertas em `ALERTA`: gatilho por **km**
(`km_atual − km_no_momento ≥ limite_km − antecedencia_km`) e por **tempo**
(`hoje − data_última ≥ limite_dias − antecedencia_dias`), descontando a antecedência. Veículo
que não pode ser avaliado (sem manutenção registrada, km não confiável, sem limiar aplicável)
gera alerta `dados_insuficientes` em vez de ser pulado. O motor é **idempotente** (deixa o
índice único parcial `ux_alerta_ativo` do banco rejeitar duplicata e trata a colisão como
no-op) e **create-only** (nunca apaga; resolução é ação manual). Um agendador embutido
(APScheduler, D4) roda em ciclo único e ordenado — `executar_ciclo()` da spec 003 e depois a
verificação de alertas — com o intervalo parametrizado por variável de ambiente.

Abordagem técnica: função importável `verificar_alertas(hoje=None) -> dict` em `alertas/motor.py`
(espelhando `executar_ciclo()`), CLI `python -m alertas.motor`, e `scheduler.py` na raiz
costurando ETL + motor num único job não-sobreposto.

## Technical Context

**Language/Version**: Python 3.12 (D1; `requires-python >=3.12` no `pyproject.toml`)

**Primary Dependencies**: SQLAlchemy 2.0 (acesso ao banco via `db.config`), **APScheduler ≥3.10,<4**
(D4 — agendador embutido; **nova dependência** a adicionar). pandas/FastAPI já presentes não são
usados pelo motor.

**Storage**: banco consolidado da spec 002 via `db.config.get_engine()`/`get_session()` —
`DATABASE_URL` (default `sqlite:///db/frota.db`; demo PostgreSQL 16). O motor lê `veiculo`,
`manutencao`, `limiar_config` e escreve `alerta`. Nunca lê staging nem arquivos-fonte.

**Testing**: pytest (já configurado; `testpaths=["tests"]`, `pythonpath=["."]`). Padrão de fixture
herdado de `tests/test_pipeline.py` (`DATABASE_URL` para sqlite em `tmp_path` + `db.init_db.main()`).

**Target Platform**: processo único Linux/macOS (contêiner `app` da spec 007); SQLite em dev,
PostgreSQL 16 na demo — mesmo código nos dois dialetos.

**Project Type**: single project (backend/CLI Python) — camadas isoladas comunicando só via banco.

**Performance Goals**: verificação < 1 ciclo após a ingestão (SC-001); volume da PoC (dezenas de
veículos × ≤4 tipos) — a verificação inteira roda em bem menos de 1 s, compatível com ciclo de 1–2 min.

**Constraints**: idempotência total (SC-002: 10 execuções → 0 duplicatas); zero constantes de
negócio no código (limiares e intervalo vêm de dados/env — constitution V); leitura de
`LIMIAR_CONFIG` a cada verificação, sem cache de processo (SC-004); no-op de conflito e contagem
de criados **dialeto-agnósticos** (learning lesson "dois bancos-alvo").

**Scale/Scope**: toda a frota do `veiculo` × tipos com linha em `LIMIAR_CONFIG` para o
`tipo_veiculo`; 3 tipos de gatilho (`km`, `tempo`, `dados_insuficientes`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Veredito |
|---|---|---|
| **I. Critério binário / demo-crítico primeiro** | US1 (km ao vivo) e US5 (ciclo agendado) são o caminho do disparo ao vivo; o plano prioriza o ponto de entrada do motor e a costura com `executar_ciclo()`. | ✅ PASS |
| **II. Rastreabilidade total** | Cada alerta km/tempo carrega `limiar_id` (rastreia até a parametrização); `dados_insuficientes` carrega `detalhe` com a causa. O motor lê consolidadas que já têm `fonte_origem`. Nenhuma rejeição silenciosa: gap de dado vira alerta explícito. | ✅ PASS |
| **III. Dado inconsistente é requisito** | `dados_insuficientes` cobre sem-manutenção, km não confiável (ADR-002) e sem-limiar-aplicável — nunca omite veículo (SC-003). | ✅ PASS |
| **IV. Conformidade (LGPD/LAI)** | O motor lê apenas km, datas e limiares; não toca `condutor_pseudo` nem qualquer dado pessoal; nada é exposto. | ✅ PASS |
| **V. Parametrização como dados** | Limiares/antecedências vêm exclusivamente de `LIMIAR_CONFIG` lida a cada verificação; intervalo do ciclo por env var. Nenhuma constante de negócio no código. | ✅ PASS |
| **VI. Camadas isoladas, só via banco, idempotência** | Motor conversa só pelo banco (nunca staging/arquivo); idempotência garantida por construção (índice único `ux_alerta_ativo` + no-op); proibido DELETE. | ✅ PASS |
| **VII. Simplicidade, open source, sem lock-in** | APScheduler embutido (zero infra extra, open source); lógica direta sem cache/estado de processo; nenhuma tabela nova. | ✅ PASS |

**Resultado**: todos os gates passam; nenhuma violação → **Complexity Tracking vazio**.

## Project Structure

### Documentation (this feature)

```text
specs/004-motor-alertas/
├── plan.md              # Este arquivo (/speckit-plan)
├── research.md          # Fase 0 (/speckit-plan) — decisões técnicas resolvidas
├── data-model.md        # Fase 1 (/speckit-plan) — visão de leitura/escrita + lógica
├── quickstart.md        # Fase 1 (/speckit-plan) — roteiro de validação US1–US5 (2 dialetos)
├── contracts/
│   └── motor_alertas.md # Fase 1 (/speckit-plan) — pontos de entrada verificar_alertas + scheduler
├── checklists/
│   └── requirements.md  # (pré-existente) qualidade da spec
└── tasks.md             # Fase 2 (/speckit-tasks — NÃO criado por /speckit-plan)
```

### Source Code (repository root)

```text
alertas/
├── __init__.py
├── motor.py             # verificar_alertas(hoje=None) -> dict + CLI (python -m alertas.motor)
├── regras.py            # (opcional) regras puras: dispara_km(), dispara_tempo(), km_confiavel()
└── alert_config.py      # intervalo_ciclo_segundos() lendo env var (constitution V)

scheduler.py             # raiz — APScheduler: 1 job ordenado (executar_ciclo() → verificar_alertas())

db/                      # (spec 002, entregue) — models.Alerta/LimiarConfig, config, init_db
pipeline/                # (spec 003, entregue) — run_etl.executar_ciclo()

tests/
└── test_alertas.py      # gatilho km, gatilho tempo, idempotência (SC-002), dados_insuficientes,
                         # edição de limiar ao vivo (SC-004), ciclo ordenado (US5)
```

**Structure Decision**: single project Python. O motor mora em `alertas/` (arquitetura §9),
espelhando a organização de `pipeline/`; o agendador é `scheduler.py` na raiz (arquitetura §9),
importando `executar_ciclo` (spec 003) e `verificar_alertas` (esta spec). Sem novas camadas nem
tabelas — reaproveita `db.config`, `db.models` e o esquema já migrado.

## Complexity Tracking

> Nenhuma violação de constituição — seção vazia.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
