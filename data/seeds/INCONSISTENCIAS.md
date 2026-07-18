# Inconsistências propositais dos datasets simulados (FR-003 · SC-002)

Gerado por `data/gerador_dados.py` (semente 42, data-âncora 2026-07-15).
Cada inconsistência é insumo das regras de qualidade do pipeline (spec 003).

## Fonte 1 — Abastecimento (CSV)

| Inconsistência | Exemplo gerado | Tratamento (spec 003) | Motivo em `log_qualidade` |
|---|---|---|---|
| Placa com e sem hífen (~50/50) | `RLL-8062` | normalização canônica (regex dual, ADR-001) | — (normaliza) |
| Datas em 2 formatos | `28/11/2025` e `2025-11-20` | parsing tolerante | `data_invalida` se não parsear |
| Litros/valor com vírgula decimal | `31,5` | conversão decimal | — (normaliza) |

## Fonte 2 — Multas (JSON/API)

| Inconsistência | Exemplo gerado | Tratamento (spec 003) | Motivo |
|---|---|---|---|
| Placa em minúsculas | `oll2058` | normalização canônica | — (normaliza) |
| `cnh` presente (dado pessoal sintético, DV inválido) | 11 dígitos | **descartada na carga** (minimização LGPD, FR-011 da spec 003) | — |
| `gravidade`/`codigo_infracao` fonte-apenas | — | ignorados na consolidação (ERD intacto) | — |

## Fonte 3 — Manutenção (XLSX, 3 abas)

| Inconsistência | Exemplo gerado | Tratamento (spec 003) | Motivo |
|---|---|---|---|
| Tipo em texto livre | `FILTROS`, `PNEUS`, `REVISAO 10000`, `REVISAO 20000`, `REVISAO 30000`, `REVISAO 60000` | vocabulário canônico (`troca_oleo`…) | `tipo_desconhecido` se não mapear |
| Categoria com grafias variadas | `Preventiva`, `CORRETIVA`, `prev.` | normaliza p/ `preventiva`\|`corretiva` | idem |
| `km_no_momento` ausente (15 registros, ~15%) | célula vazia | aceito (nullable); motor trata como km não confiável | — |
| Datas TEXT × serial Excel | `2026-03-15` / `46068` | parsing tolerante | `data_invalida` |

**Anomalias protegidas**: nunca recebem km ausente — os registros-âncora dos 2 veículos
da demo, as revisões programadas de garantia **e o evento mais recente de cada
(placa, tipo de manutenção)**, que é o que o motor usa em `km_desde_ultima`. Isso preserva
o invariante "demais veículos longe dos limiares, sem alertas espúrios" (ADR-003, adendo
2026-07-15b; regressão coberta por `test_sem_alertas_espurios`).

## Fonte 4 — Licenciamento (SQLite)

| Inconsistência | Exemplo gerado | Tratamento (spec 003) | Motivo |
|---|---|---|---|
| Placas duplicadas (8 veículos c/ 2 registros) | `JRQ6J90` | dedup por (placa, vencimento mais recente) | `duplicado` |
| Vencimento em 3 formatos | `dd/mm/aaaa` TEXT · `aaaa-mm-dd` TEXT · serial INTEGER | parsing tolerante | `data_invalida` |
| **2 vencimentos com dia fora do calendário oficial** (vencendo em ≤7 dias da âncora — FR-010) | — | data válida, mês pode divergir do final da placa (legado) | — |

## Invariantes de coerência (SC-005/SC-006 — não são inconsistências)

- Hodômetro monotônico por veículo, consistente entre CSV e XLSX (mapeamento km↔data linear na janela).
- Consumo derivado dentro das faixas por tipo; valores de multa ∈ tabela CTB.
- Razão de custo corretiva ÷ preventiva calibrada em 3–5× (benchmark do pitch, spec 007).
