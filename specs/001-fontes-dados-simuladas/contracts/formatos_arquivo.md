# Contratos — Formatos de Arquivo das Fontes Simuladas

**Branch**: `feature/001-fontes-dados-simuladas` | **Date**: 2026-07-14

Contratos de formato dos arquivos gerados por `data/gerador_dados.py` para as Fontes 1, 3 e 4
(a Fonte 2 — multas — é servida por API; ver `contracts/api_multas.md`). O pipeline (spec 003)
confia nestes contratos ao construir os extratores.

Cada fonte é **deliberadamente heterogênea** (arquitetura §2, constitution III): formato,
delimitador, separador decimal e grafia da placa diferentes por fonte. As inconsistências
propositais estão listadas em `data/seeds/INCONSISTENCIAS.md` (gerado pelo `gerador_dados.py`).

---

## Fonte 1 — Abastecimento (CSV)

**Arquivo**: `data/seeds/abastecimento.csv`
**Delimitador**: `,` (vírgula)
**Encoding**: UTF-8
**Cabeçalho**: sim (primeira linha)

```csv
placa,data,litros,valor,condutor,km
ABC-1234,14/07/2026,45,5,350,75,COND-042,4400
ABC1234,2026-07-14,40,0,312,00,COND-007,8200
```

**Contrato de colunas**:

| Coluna | Tipo no CSV | Obrigatório | Formato / Inconsistência |
|---|---|---|---|
| `placa` | string | sim | ~50% com hífen (`ABC-1234`), ~50% sem (`ABC1234`). Pipeline normaliza para `AAA9999`. |
| `data` | string | sim | Mistura `dd/mm/aaaa` e `aaaa-mm-dd`. Pipeline faz parsing tolerante. |
| `litros` | string | sim | Vírgula decimal (`45,5`). Pipeline converte para float. |
| `valor` | string | sim | Vírgula decimal (`350,75`). Pipeline converte para float. |
| `condutor` | string | sim | `COND-NNN` (pseudônimo, sem inconsistência — LGPD desde a origem). |
| `km` | string | sim | Inteiro como texto (`4400`). Hodômetro lido no posto (clarificação 2026-07-14). Usado pelo pipeline para atualizar `veiculo.km_atual`; **não persistido** na tabela consolidada `ABASTECIMENTO`. |

**Arquivo especial — Gatilho da demo**: `data/seeds/gatilho_demo_abastecimento.csv`
Mesmo contrato de colunas. Contém 1 registro para o veículo da demo A, com `km` elevando
`km_atual` para ≥ 4501 (cruzando `limite_km - antecedencia_km = 4500`). Depositado em
`data/inbox/` na apresentação.

---

## Fonte 3 — Manutenção (XLSX multi-abas)

**Arquivo**: `data/seeds/manutencao.xlsx`
**Engine**: openpyxl (escrita via `pandas.ExcelWriter`)
**Abas**: 3 (`Oficina Central`, `Oficina Regional Norte`, `Manutenção Terceirizada`)
**Cabeçalho**: sim (primeira linha de cada aba)

**Contrato de colunas (idêntico em todas as abas)**:

| Coluna | Tipo no XLSX | Obrigatório | Formato / Inconsistência |
|---|---|---|---|
| `placa` | string | sim | Maiúsculas sem hífen (`ABC1234`) — canônico (esta fonte é "limpa" em placa). |
| `data` | string OU integer | sim | Mistura: `aaaa-mm-dd` (TEXT) e serial Excel (INTEGER, ex.: `46068`). Pipeline tenta ambos. |
| `tipo` | string | sim | Texto livre não padronizado: `troca de oleo`, `Troca Óleo`, `TROCA_OLEO`, `troca óleo`. Pipeline normaliza para `troca_oleo` \| `filtros` \| `pneus` \| `revisao_geral`. |
| `km_no_momento` | integer OU vazio | não | ~15% dos registros com km ausente (célula vazia). Motor gera `dados_insuficientes` quando aplicável (spec 004). |
| `valor` | float | sim | Ponto decimal (`280.50`) — difere do CSV de abastecimento (vírgula). |

**Posicionamento da demo**: a última `troca_oleo` (aba `Oficina Central`) do veículo A tem
`km_no_momento` tal que `km_atual - km_no_momento = 4400`. A última `troca_oleo` do veículo B
tem `data` há 166 dias (cruzou antecedência 165, não o limite 180).

---

## Fonte 4 — Licenciamento (SQLite)

**Arquivo**: `data/seeds/licenciamento.sqlite`
**Acesso**: `sqlite3` stdlib ou SQLAlchemy com `sqlite:///data/seeds/licenciamento.sqlite`
**Tabela**: `licenciamento` (única tabela, sem PRIMARY KEY — espelha "banco legado frouxo")

**Contrato de colunas**:

| Coluna | Tipo SQLite | Obrigatório | Formato / Inconsistência |
|---|---|---|---|
| `placa` | TEXT | sim | Maiúsculas sem hífen (`ABC1234`), mas com **duplicatas** (~20% dos veículos têm 2 linhas: vencimento antigo + atual). Pipeline deduplica por `(placa, vencimento mais recente)`. |
| `vencimento` | TEXT OU INTEGER | sim | Formatos mistos: `dd/mm/aaaa` (TEXT), `aaaa-mm-dd` (TEXT), serial Excel (INTEGER). Pipeline faz parsing tolerante. |
| `situacao` | TEXT | sim | `em_dia` \| `vencido` (vocabulário já padronizado nesta fonte). |

**Esquema SQL** (criado pelo gerador — sem chaves, propositalmente frouxo):
```sql
CREATE TABLE licenciamento (
    placa       TEXT NOT NULL,
    vencimento  TEXT,
    situacao    TEXT
);
```

---

## Cadastro base e limiares-semente (referências internas)

**`data/seeds/veiculos.json`** — cadastro canônico de 40 veículos. Não é uma fonte legada;
é a referência interna usada pelo gerador para derivar as 4 fontes. Ver `data-model.md`
§ Cadastro base para o schema completo.

**`data/seeds/limiares_semente.json`** — tabela-semente de 9 linhas de limiares, usada para
posicionar os veículos da demo. Espelha os valores que a spec 002 formalizará em
`LIMIAR_CONFIG`. Ver `data-model.md` § Limiares-semente e `plan.md` § Complexity Tracking
para a justificativa de duplicação local.

---

## Documentação das inconsistências (FR-003)

**Arquivo**: `data/seeds/INCONSISTENCIAS.md` — gerado pelo `gerador_dados.py`, lista cada
inconsistência propositais por fonte, com exemplo concreto extraído dos dados gerados,
referência à regra de qualidade que a trata (spec 003) e o motivo de rejeição esperado em
`log_qualidade` (quando aplicável). Este arquivo é a evidência verificável para SC-002.
