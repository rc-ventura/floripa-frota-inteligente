# Proteja a âncora do ruído: em geradores de dados sintéticos, o registro que carrega o invariante é imune à injeção de anomalias

**Context:** Descoberto no ciclo 1 do `sdd-final-review` da spec 001 (`feature/001-fontes-dados-simuladas`) — bug HIGH encontrado pelo QA Engineer, corroborado por análise externa (Devin) e reproduzido pelo Tech Leader.
**Date:** 2026-07-15
**Future intent:** aplicar como checklist em todo gerador de fixture/dados sintéticos do projeto (e no pipeline da spec 003, que também injeta/trata anomalias): identificar quais registros carregam semântica de invariante e blindá-los ANTES de escrever o injetor de ruído.

---

## Mental Model: ruído × semântica de âncora

Um gerador de dados realista tem duas forças em tensão:

```
  INJETOR DE RUÍDO                      INVARIANTE DE NEGÓCIO
  "15% dos km ficam ausentes"           "nenhum veículo não-demo dispara alerta"
        │                                       │
        └──────────────┬────────────────────────┘
                       ▼
            EVENTO-ÂNCORA (maior km por placa×tipo)
            = o registro que o CONSUMIDOR (motor de alertas)
              usa para calcular km_desde_ultima
```

O ruído era sorteado uniformemente sobre os eventos "não protegidos" — mas a proteção
cobria apenas as âncoras da *demo* e os marcos de garantia. Quando o sorteio anulava o
km da âncora de um veículo comum, o cálculo do motor caía no evento *anterior* e o
`km_desde_ultima` saltava acima do gatilho (ex.: `QSC3784` foi de ~3.000 para 8.309 km
contra gatilho de 4.500) — alerta espúrio que o apresentador não saberia explicar na demo.

**A regra:** o conjunto "protegido do ruído" não é uma lista de casos especiais; é
derivado da **semântica do consumidor**. Se o consumidor usa `max(km) por (placa, tipo)`,
então `max(km) por (placa, tipo)` é imune ao ruído — para *todos* os veículos, sempre.

| Camada | Onde age | O que cobre | O que NÃO cobre |
|---|---|---|---|
| Proteção por caso especial (`ancora_demo=True`) | eventos marcados na criação | demo A/B, marcos de garantia | âncoras dos 38 veículos comuns ← **o bug** |
| Proteção semântica (`max km por placa×tipo`) | pool do injetor, pós-geração | qualquer evento que SEJA âncora, hoje e após refactors | ruído em eventos não-âncora (desejado) |

## O segundo erro: testar só o invariante positivo

A suíte tinha 9 asserções ricas de coerência (monotonicidade, faixas de consumo, tabela
CTB...) — todas sobre propriedades *construídas de propósito*. O invariante violado era
**emergente** (interação ruído × âncora) e não tinha teste, porque ninguém o construiu:
ele era uma *ausência* prometida ("sem alertas espúrios"). Lição de design de teste:

- Propriedade construída → o teste confirma a construção (fácil de lembrar).
- Propriedade **negativa/emergente** ("nunca acontece X") → o teste precisa simular o
  consumidor e varrer todo o dataset (fácil de esquecer — é onde os bugs moram).

## Exemplo do projeto (o fix)

`data/gerador_dados.py` — o pool do injetor passou a excluir a âncora semântica:

```python
ancora_por_par: dict[tuple[str, str], dict] = {}
for e in eventos:
    chave = (e["placa"], e["_tipo_canonico"])
    atual = ancora_por_par.get(chave)
    if atual is None or e["km_no_momento"] > atual["km_no_momento"]:
        ancora_por_par[chave] = e
ids_ancora = {id(e) for e in ancora_por_par.values()}
elegiveis = [e for e in eventos if not e["_protegido"] and id(e) not in ids_ancora]
```

`tests/test_gerador_dados.py::test_sem_alertas_espurios` — o teste do invariante
negativo simula o cálculo do motor (spec 004) para cada veículo não-demo × tipo
aplicável e exige `km_desde < limite−antecedência` e `dias_desde < limite−antecedência`.
Critério de aceite do Tech Leader honrado: **falhava antes do fix, passa depois**.

**Divisão de responsabilidade:**
- Gerador: garante a propriedade nos dados (proteção semântica no pool).
- Teste de regressão: prova a propriedade simulando o consumidor real.

## Relation to ADRs and next steps

- **ADR-003, item 10 (adendo 2026-07-15b)** — formaliza a decisão: km-ausente nunca recai
  sobre o evento de maior km por (placa, tipo).
- **Spec 003 (pipeline)** — mesma lição se aplica na direção inversa: as regras de
  qualidade tratarão ruído; testar também o que *não* pode acontecer (ex.: rejeição nunca
  silenciosa, dedup nunca remove a ocorrência mais recente).
- **Spec 004 (motor)** — o teste de regressão daqui é um esboço fiel da lógica do motor;
  reaproveitar as asserções como casos de teste unitário dos gatilhos.
