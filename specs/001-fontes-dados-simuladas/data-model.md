# Data Model — Fontes de Dados Simuladas (Spec 001)

**Branch**: `feature/001-fontes-dados-simuladas` | **Date**: 2026-07-14

Este documento descreve o **shape de cada fonte simulada** gerada por `data/gerador_dados.py`
— ou seja, a estrutura dos arquivos que o pipeline (spec 003) vai ingerir. **Não** descreve o
schema do banco consolidado (isso é a spec 002, `LIMIAR_CONFIG`/`VEICULO`/`ABASTECIMENTO`/...).

As fontes são **deliberadamente heterogêneas** (arquitetura §2, constitution III): cada uma
tem formato, padrão e inconsistências próprias. A placa é a chave de reconciliação, grafada
de formas diferentes em cada fonte (ver `research.md` R7).

---

## Cadastro base (referência interna do gerador)

**Arquivo**: `data/seeds/veiculos.json` (não é uma das 4 fontes legadas; é o cadastro
canônico que o gerador usa para derivar as 4 fontes com grafias divergentes).

```json
[
  {
    "placa": "ABC1D23",            // canônico: Mercosul AAA9A99 (~70%) ou antigo AAA9999 (~30%) — ADR-001
    "tipo_veiculo": "leve",        // leve | ambulancia | caminhao
    "modelo": "Fiat Strada",       // catálogo real de frota municipal por tipo (R13)
    "ano": 2021,                   // distribuído ~2015–2026 (R13)
    "em_garantia": false,          // true quando ano >= 2023 (~25% da frota — R13)
    "secretaria": "Saúde",         // sintético
    "km_atual": 4400,              // para veículo da demo A; demais: derivado do modelo de consumo (R12)
    "km_mes": 1500,                // km/mês sorteado na faixa do tipo (R12) — base da série de hodômetro
    "demo_gatilho": true,          // true para os 2 veículos da demo (índices 0 e 1)
    "demo_gatilho_tipo": "km",     // "km" | "tempo" | null
    "custo_desproporcional": false, // true para exatamente 1 leve fora da demo (FR-009, R12)
    "condutores": ["COND-012", "COND-019"]  // pool sintético do veículo (FR-004) — usado por abastecimento e multas
  }
]
```

**Regras de validação (internas do gerador)**:
- 40 veículos: ≈30 leves, 6 ambulâncias, 4 caminhões (decisão 2026-07-14).
- Placas únicas, formato `^[A-Z]{3}\d[A-Z\d]\d{2}$` (cobre antigo `AAA9999` e Mercosul
  `AAA9A99`); mistura ~70% Mercosul / ~30% antigo (ADR-001).
- Exatamente 1 veículo leve (fora dos índices 0 e 1) com `custo_desproporcional=true`:
  consumo no piso da faixa, corretivas extras e multas concentradas (FR-009, R12).
- Marca/modelo sorteados do catálogo real por tipo (R13); `em_garantia=true` quando
  `ano ≥ 2023` (~25% da frota) — esses veículos fazem revisões programadas nos marcos do
  fabricante (FR-012/FR-013).
- Veículo índice 0: `demo_gatilho=true`, `demo_gatilho_tipo="km"`, `km_atual=4400`.
- Veículo índice 1: `demo_gatilho=true`, `demo_gatilho_tipo="tempo"`, `km_atual` aleatório
  dentro do limite; última `troca_oleo` há 166 dias (cruzou antecedência 165, não o limite 180).
- Demais 38: `demo_gatilho=false`, `km_atual` e datas de manutenção aleatórios *longe* dos
  limiares (sem alertas espúrios).

---

## Fonte 1 — Abastecimento (CSV)

**Arquivo**: `data/seeds/abastecimento.csv`
**Volume**: ~1.500 registros (derivado do modelo de consumo por tipo de veículo — R12).

| Coluna | Tipo (no CSV) | Exemplo | Inconsistência propositais |
|---|---|---|---|
| `placa` | TEXT | `ABC-1D23` / `ABC1D23` / `ABC-1234` | ~50% com hífen, ~50% sem hífen (mistura; formatos Mercosul e antigo conforme o cadastro) |
| `data` | TEXT | `14/07/2026` / `2026-07-14` | Mistura de `dd/mm/aaaa` e `aaaa-mm-dd` |
| `litros` | TEXT | `45,5` | Vírgula decimal (não ponto); derivados do trecho rodado ÷ consumo do veículo (R12) |
| `valor` | TEXT | `350,75` | Vírgula decimal |
| `condutor` | TEXT | `COND-042` | Pseudônimo (sem inconsistência — LGPD desde a origem) |
| `km` | TEXT | `4400` | Hodômetro lido no posto, **monotônico crescente** por veículo (R12); o pipeline atualiza `veiculo.km_atual` **e persiste** como `km_hodometro` no consolidado (ADR-002) |

**Arquivo especial — Gatilho da demo**: `data/seeds/gatilho_demo_abastecimento.csv`
Mesma estrutura de colunas. Contém **1 registro** para o veículo da demo A (índice 0): um
abastecimento cujo `km` eleva `km_atual` de 4400 para ≥ 4501, cruzando o limiar de
antecedência (`limite_km - antecedencia_km = 5000 - 500 = 4500`). Depositado em
`data/inbox/` durante a apresentação para disparar o alerta ao vivo.

---

## Fonte 2 — Multas (JSON servido por API)

**Arquivo**: `fake_api/multas.json` (servido por `fake_api/main.py`, ver `contracts/api_multas.md`)
**Volume**: ~100 registros, distribuição **enviesada** por veículo/condutor (concentrada em
poucos, incluindo o veículo de `custo_desproporcional` — R10/R12).

```json
[
  {
    "placa": "abc1d23",            // minúsculas, sem hífen (inconsistência propositais)
    "data": "2026-05-20",          // aaaa-mm-dd
    "gravidade": "media",          // leve | media | grave | gravissima (sorteada — R10)
    "valor": 130.16,               // derivado da gravidade: tabela CTB (88.38 | 130.16 | 195.23 | 293.47 e multiplicadores) — R10
    "condutor": "COND-042",        // pseudônimo
    "cnh": "01234567890",          // 11 dígitos sintéticos, DV propositalmente inválido (research R2)
    "situacao": "pendente",        // pendente | paga
    "codigo_infracao": "7455-1"    // código do enquadramento (Portaria 354/2022, Bloco 5)
  }
]
```

> Na carga consolidada, o pipeline (spec 003) persiste apenas os campos do ERD (`placa`,
> `data`, `valor`, `condutor_pseudo`, `situacao`, `fonte_origem`); `cnh`, `gravidade` e
> `codigo_infracao` são fonte-apenas (ADR-003).

**Inconsistências propositais**: placa em minúsculas; campo `cnh` presente (dado pessoal —
espelha Bloco 3 do AIT, Portaria SENATRAN 354/2022). O pipeline (spec 003) descarta `cnh` na
carga consolidada e persiste só `condutor_pseudo` (LGPD, constitution IV).

**Validação**: nenhum nome, CPF ou CNH real (SC-003). O `cnh` sintético não passa na
validação oficial de checksum (módulo 11) — obviamente não-real.

---

## Fonte 3 — Manutenção (XLSX multi-abas)

**Arquivo**: `data/seeds/manutencao.xlsx`
**Volume**: ~250–300 registros distribuídos em 3 abas (cadência derivada dos limiares × km/mês
do veículo, + corretivas — R12; o veículo de `custo_desproporcional` recebe 2–3 corretivas
extras de valor alto). Veículos `em_garantia` registram **revisões programadas nos marcos
do fabricante** (10.000 km/12 meses) na aba `Manutenção Terceirizada`, com grafias como
"Revisão 10.000 km" (R13). Corretivas calibradas a 3–5× o valor médio das preventivas
(benchmark do pitch — spec 007).

**Abas** (cada uma espelha uma oficina/setor diferente, com padrões de texto inconsistentes):
1. `Oficina Central`
2. `Oficina Regional Norte`
3. Manutenção Terceirizada`

**Estrutura de colunas (mesma em todas as abas)**:

| Coluna | Tipo (no XLSX) | Exemplo | Inconsistência propositais |
|---|---|---|---|
| `placa` | TEXT | `ABC1D23` / `ABC1234` | Maiúsculas sem hífen (canônico — esta fonte é a "limpa" em termos de placa) |
| `data` | TEXT / serial Excel | `2026-03-15` / `46068` | Mistura de `aaaa-mm-dd` (TEXT) e serial Excel (INTEGER) |
| `tipo` | TEXT | `troca de oleo` / `Troca Óleo` / `Revisão 10.000 km` | Texto livre, sem padronização (normaliza para o vocabulário canônico no pipeline; grafias de revisão programada → `revisao_geral` — R13) |
| `categoria` | TEXT | `preventiva` / `Preventiva` / `CORRETIVA` / `prev.` | Grafias variadas (normaliza para `preventiva` \| `corretiva`); **persistida no consolidado** (ADR-003 item 7) |
| `km_no_momento` | INTEGER / vazio | `4400` / `(vazio)` | Interpolado da **mesma série de hodômetro** dos abastecimentos (R12); ausente em ~15% dos registros (anomalia propositais — gera `dados_insuficientes` no motor se aplicável) |
| `valor` | FLOAT | `280.50` | Ponto decimal (difere do CSV de abastecimento); corretivas 3–5× o médio das preventivas (R13) |

**Regras de posicionamento da demo**: a última `troca_oleo` do veículo A (índice 0) tem
`km_no_momento` tal que `km_atual - km_no_momento = 4400` (faltam 600 para o limite 5000).
A última `troca_oleo` do veículo B (índice 1) tem `data` há 166 dias (cruzou antecedência 165).

---

## Fonte 4 — Licenciamento (SQLite)

**Arquivo**: `data/seeds/licenciamento.sqlite`
**Volume**: ~48 registros (40 veículos + ~8 duplicatas).

**Tabela**: `licenciamento`

| Coluna | Tipo (SQLite) | Exemplo | Inconsistência propositais |
|---|---|---|---|
| `placa` | TEXT | `ABC1D23` / `ABC1234` | Maiúsculas sem hífen, mas com **duplicatas** (~20% dos veículos têm 2 registros: vencimento antigo + atual) |
| `vencimento` | TEXT / INTEGER | `15/08/2026` / `2026-08-15` / `46042` | Formatos mistos: `dd/mm/aaaa` (TEXT), `aaaa-mm-dd` (TEXT), serial Excel (INTEGER). Data coerente com o **final da placa** (calendário DETRAN-SC: final 1 → 31/03 ... final 0 → 30/12 — R11) |
| `situacao` | TEXT | `em_dia` / `vencido` | Sem inconsistência (vocabulário já padronizado nesta fonte); ≥2 registros **vencidos** e ≥2 **vencendo em ≤7 dias** para o semáforo da spec 005 (FR-010, R11) — nenhum deles entre os 2 veículos da demo |

**Esquema SQL** (criado pelo gerador):
```sql
CREATE TABLE licenciamento (
    placa       TEXT NOT NULL,
    vencimento  TEXT,  -- tipo frouxo: aceita TEXT e INTEGER (serial Excel)
    situacao    TEXT
);
-- Sem PRIMARY KEY propositalmente — espelha "banco legado sem modelagem cuidadosa"
-- e permite as duplicatas propositais.
```

---

## Limiares-semente (referência de posicionamento)

**Arquivo**: `data/seeds/limiares_semente.json` (espelha os valores que a spec 002
formalizará em `LIMIAR_CONFIG`; ver `plan.md` § Complexity Tracking para a justificativa
de duplicação local).

```json
[
  {"tipo_veiculo": "leve", "tipo_manutencao": "troca_oleo", "limite_km": 5000, "limite_dias": 180, "antecedencia_km": 500, "antecedencia_dias": 15},
  {"tipo_veiculo": "leve", "tipo_manutencao": "filtros", "limite_km": 5000, "limite_dias": 180, "antecedencia_km": 500, "antecedencia_dias": 15},
  {"tipo_veiculo": "leve", "tipo_manutencao": "pneus", "limite_km": 40000, "limite_dias": 720, "antecedencia_km": 2000, "antecedencia_dias": 30},
  {"tipo_veiculo": "leve", "tipo_manutencao": "revisao_geral", "limite_km": 10000, "limite_dias": 365, "antecedencia_km": 1000, "antecedencia_dias": 30},
  {"tipo_veiculo": "ambulancia", "tipo_manutencao": "troca_oleo", "limite_km": 5000, "limite_dias": 180, "antecedencia_km": 500, "antecedencia_dias": 15},
  {"tipo_veiculo": "ambulancia", "tipo_manutencao": "revisao_geral", "limite_km": 10000, "limite_dias": 365, "antecedencia_km": 1000, "antecedencia_dias": 30},
  {"tipo_veiculo": "caminhao", "tipo_manutencao": "troca_oleo", "limite_km": 10000, "limite_dias": 180, "antecedencia_km": 1000, "antecedencia_dias": 15},
  {"tipo_veiculo": "caminhao", "tipo_manutencao": "pneus", "limite_km": 60000, "limite_dias": 720, "antecedencia_km": 3000, "antecedencia_dias": 30},
  {"tipo_veiculo": "caminhao", "tipo_manutencao": "revisao_geral", "limite_km": 30000, "limite_dias": 365, "antecedencia_km": 1500, "antecedencia_dias": 30}
]
```

---

## Relacionamentos entre as fontes

As 4 fontes não têm chaves estrangeiras entre si (são sistemas legados isolados). A
reconciliação acontece no pipeline (spec 003) via **normalização da placa** para o formato
canônico — maiúsculas, sem hífen, nos dois padrões vigentes (`AAA9999` antigo e `AAA9A99`
Mercosul; regex `^[A-Z]{3}\d[A-Z\d]\d{2}$`, ADR-001). O diagrama abaixo mostra a relação
lógica (não física):

```mermaid
flowchart LR
    CAD["veiculos.json<br/>(cadastro base, placa canônica)"]
    F1["abastecimento.csv<br/>placa: hífen misturado"]
    F2["multas.json<br/>placa: minúsculas"]
    F3["manutencao.xlsx<br/>placa: canônica"]
    F4["licenciamento.sqlite<br/>placa: canônica + duplicatas"]
    CAD --> F1
    CAD --> F2
    CAD --> F3
    CAD --> F4
    F1 -. normaliza placa .-> CAN["canônico: AAA9999 | AAA9A99<br/>(no pipeline, spec 003)"]
    F2 -. normaliza placa .-> CAN
    F3 -. normaliza placa .-> CAN
    F4 -. normaliza placa + deduplica .-> CAN
```

## Estados / transições

Esta spec não tem transições de estado de domínio (é um gerador de arquivos estáticos). O
único "estado" é a marca `demo_gatilho` no cadastro base (estático, não muda). Transições de
estado (alerta ativo → resolvido, situação da multa pendente → paga) são concerns das specs
004 (motor) e 002 (modelo consolidado), não desta.
