# Phase 1 — Data Model: Motor de Alertas Preventivos

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

O motor **não cria tabela nem migration nova** — o esquema (`ALERTA`, `LIMIAR_CONFIG`,
`VEICULO`, `MANUTENCAO`, `ABASTECIMENTO`) já foi entregue pela spec 002. Este documento fixa a
**visão do motor** sobre esse esquema: o que ele lê, o que ele escreve e a lógica de avaliação
que transforma um em outro. Definições canônicas de coluna/tipo/constraint estão em
`db/models.py` e em `specs/002-modelo-dados-banco/data-model.md`.

---

## 1. Entidades lidas (somente leitura)

### `veiculo` (dimensão)
| Campo usado | Uso no motor |
|---|---|
| `placa` (PK) | identidade do veículo avaliado; FK de `alerta` |
| `tipo_veiculo` (`leve`\|`ambulancia`\|`caminhao`) | seleciona quais linhas de `limiar_config` se aplicam |
| `km_atual` (int, ≥0) | operando do gatilho por km (`km_desde = km_atual − km_no_momento`) |

### `manutencao` (fato)
| Campo usado | Uso no motor |
|---|---|
| `placa`, `tipo` (`troca_oleo`\|`filtros`\|`pneus`\|`revisao_geral`) | agrupa "última por (placa, tipo)" (índice `ix_manutencao_placa_tipo_data`) |
| `data` | operando do gatilho por tempo (`dias_desde = hoje − data`); seleciona a última (maior `data`) |
| `km_no_momento` (int, nullable) | base do gatilho por km; ausente ⇒ km não avaliável (R5) |

> `categoria` (preventiva/corretiva) e `valor` **não** são usados pelo motor (são dos painéis 006).

### `limiar_config` (parametrização — lida a cada verificação, sem cache — SC-002/FR-002)
| Campo | Uso |
|---|---|
| `id` (PK) | gravado em `alerta.limiar_id` (rastreabilidade — constitution II) |
| `tipo_veiculo`, `tipo_manutencao` | chave lógica `(tipo_veiculo, tipo_manutencao)` que casa com o veículo |
| `limite_km`, `antecedencia_km` | gatilho km: dispara se `km_desde ≥ limite_km − antecedencia_km` |
| `limite_dias`, `antecedencia_dias` | gatilho tempo: dispara se `dias_desde ≥ limite_dias − antecedencia_dias` |

**Regra-mestre (contrato spec 002)**: par `(tipo_veiculo, tipo_manutencao)` **sem linha** =
não-avaliável para aquele par. Nunca há default silencioso.

### `abastecimento` (fato — evidência opcional)
| Campo | Uso |
|---|---|
| `placa`, `data`, `km_hodometro` | evidência opcional de km não confiável (série decrescente, ADR-002) para enriquecer o `detalhe`; **não** é regra dura (R5) |

---

## 2. Entidade escrita: `alerta`

Única tabela de escrita do motor. Colunas (de `db/models.py`):

| Coluna | Tipo | Preenchimento pelo motor |
|---|---|---|
| `id` | int PK auto | banco |
| `placa` | str(7) FK→veiculo | veículo avaliado |
| `limiar_id` | int FK→limiar_config, **nullable** | `id` do limiar que disparou (km/tempo); **NULL** em `dados_insuficientes` |
| `tipo_gatilho` | `km` \| `tempo` \| `dados_insuficientes` (CHECK) | o gatilho que originou o alerta |
| `gerado_em` | datetime | `datetime.now()` no instante da criação |
| `situacao` | `ativo` \| `resolvido` (CHECK, default `ativo`) | sempre `ativo` na criação; `resolvido` só por ação manual (R7) |
| `detalhe` | str, nullable | causa/legível — obrigatório em `dados_insuficientes`; opcional (contexto) em km/tempo |

### Invariantes de escrita (garantidos por banco + motor)
- **Unicidade de alerta ativo** — índice parcial `ux_alerta_ativo (placa, tipo_gatilho,
  coalesce(limiar_id,-1)) WHERE situacao='ativo'`: no máximo **um** alerta ativo por
  `(placa, tipo_gatilho, limiar)`. `dados_insuficientes` tem `limiar_id` NULL → sentinela `-1`
  → **um** ativo por placa (R6).
- **Idempotência (FR-003/SC-002)** — o motor insere em **lote por `tipo_gatilho`** com
  `ON CONFLICT DO NOTHING`, deixando o índice tratar a colisão como **no-op**; contagens vêm do
  delta de `COUNT` (nunca `rowcount`) e `ja_ativos = candidatos − criados` (R4, **ADR-006**).
- **Histórico permanente (FR-004)** — motor **nunca** faz DELETE nem UPDATE de `alerta`; só INSERT.
  Recorrência após `resolvido` cria nova linha `ativo` (o índice parcial só vê ativos).
- **Rastreabilidade (constitution II)** — km/tempo sempre com `limiar_id` (liga ao parâmetro);
  `dados_insuficientes` sempre com `detalhe` não-vazio.

---

## 3. Lógica de avaliação (pseudocódigo canônico)

Corresponde à arquitetura §5.1 + decisões R5/R6/R7. `hoje` é injetável (R3).

```text
para cada veiculo V em veiculo:
    limiares_V = limiar_config WHERE tipo_veiculo == V.tipo_veiculo   # lido a cada verificação
    impedimentos = []            # causas de dados_insuficientes deste veículo

    se limiares_V vazio:
        impedimentos.add(f"sem limiar parametrizado para tipo_veiculo={V.tipo_veiculo}")

    para cada L em limiares_V:                       # L.tipo_manutencao é "avaliável"
        ultima = ultima_manutencao(V.placa, L.tipo_manutencao)   # ORDER BY data DESC LIMIT 1
        se ultima is None:
            impedimentos.add(f"{L.tipo_manutencao}: sem manutenção registrada")
            continua                                  # nem km nem tempo avaliáveis

        # --- gatilho por TEMPO (só precisa da data) ---
        dias_desde = (hoje - ultima.data).days
        se dias_desde >= L.limite_dias - L.antecedencia_dias:
            criar_alerta(V.placa, tipo_gatilho="tempo", limiar_id=L.id,
                         detalhe=f"{L.tipo_manutencao}: {dias_desde}d desde {ultima.data}")

        # --- gatilho por KM (precisa de km confiável — R5) ---
        se km_confiavel(V.km_atual, ultima.km_no_momento):
            km_desde = V.km_atual - ultima.km_no_momento
            se km_desde >= L.limite_km - L.antecedencia_km:
                criar_alerta(V.placa, tipo_gatilho="km", limiar_id=L.id,
                             detalhe=f"{L.tipo_manutencao}: {km_desde}km desde a última")
        senão:
            impedimentos.add(f"{L.tipo_manutencao}: km não confiável "
                             f"(km_atual={V.km_atual}, km_no_momento={ultima.km_no_momento})")

    se impedimentos não vazio:
        criar_alerta(V.placa, tipo_gatilho="dados_insuficientes", limiar_id=None,
                     detalhe="; ".join(impedimentos))
```

Onde:

```text
km_confiavel(km_atual, km_no_momento):
    return km_atual is not None and km_atual > 0
           and km_no_momento is not None
           and km_atual >= km_no_momento     # odômetro não anda para trás (ADR-002)

inserir_alertas(candidatos):                  # R4 — INSERT em lote (ADR-006)
    para cada grupo por tipo_gatilho:
        antes  = COUNT(*) em alerta
        INSERT do grupo ... ON CONFLICT DO NOTHING   # ux_alerta_ativo faz o no-op
        depois = COUNT(*) em alerta
        criados_<tipo_gatilho> = depois - antes      # inserts efetivos, nunca rowcount
    ja_ativos = len(candidatos) - soma(criados_*)     # o que colidiu era ativo preexistente
```

> **Nota de mecanismo (ADR-006)**: o pseudocódigo acima descreve o INSERT em lote **efetivamente
> implementado**. Uma alternativa equivalente — SAVEPOINT por linha (`begin_nested` + rollback em
> `IntegrityError`) — fica documentada no ADR-006 como plano de saída se algum dia dois candidatos
> puderem colidir dentro do **mesmo** ciclo (hoje isso não ocorre; ver o invariante no ADR).

**Observações de correção**
- Um veículo pode gerar simultaneamente `km`, `tempo` (tipos/pares distintos) e um único
  `dados_insuficientes` — todos com `tipo_gatilho`/`limiar_id` distintos, sem colisão no índice.
- Duas condições verdadeiras (km **e** tempo) para o mesmo par → dois alertas distintos (edge case).
- `detalhe` **não** entra na chave; num no-op ele não é reescrito (idempotência estrita — R4/R6).

---

## 4. Fronteiras do modelo (o que o motor NÃO faz)

- Não escreve em `veiculo`, `manutencao`, `abastecimento`, `limiar_config`, staging ou
  `log_qualidade` — só lê o consolidado e escreve `alerta` (constitution VI).
- Não lê arquivos-fonte nem staging (FR-007).
- Não resolve/apaga alertas (R7) — resolução é ação manual (painel/script, fora do escopo).
- Não cria/migra esquema — pré-requisito é `python -m db.init_db` (contrato spec 002).

---

## 5. Cenário determinístico da demo (dados de referência)

Dos seeds (`data/seeds/veiculos.json`, `limiares_semente.json`) — validam US1 e US2:

| Veículo | tipo_veiculo | gatilho | Base | Limiar (`leve`/`troca_oleo`) | Efeito esperado |
|---|---|---|---|---|---|
| `RLL8062` | leve | **km** (ao vivo) | `km_atual` sobe ao depositar `gatilho_demo_abastecimento.csv` (km 54150) | `limite_km=5000, antecedencia_km=500` | após a ingestão, `km_desde ≥ 4500` cruza a janela → alerta `km` no ciclo seguinte (SC-001) |
| `TND8453` | leve | **tempo** (sozinho) | última manutenção ~166 dias antes de `hoje` | `limite_dias=180, antecedencia_dias=15` → 165 | `166 ≥ 165` → alerta `tempo` já no 1º ciclo, sem manipulação (US2) |

> Os valores exatos vivem nos seeds (não no código nem em testes — os testes leem os seeds,
> conforme padrão de `tests/test_pipeline.py::_veiculo_demo_km`).
