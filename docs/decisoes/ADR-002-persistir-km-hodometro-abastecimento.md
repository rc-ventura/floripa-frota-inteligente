# ADR-002: Persistir o km do hodômetro na tabela consolidada `ABASTECIMENTO`

**Status**: Proposta — ratifica com o merge deste MR em `dev`
**Data**: 2026-07-14
**Specs relacionadas**: [001-fontes-dados-simuladas](../../specs/001-fontes-dados-simuladas/spec.md) (produz o km na fonte), [002-modelo-dados-banco](../../specs/002-modelo-dados-banco/spec.md) (materializa a coluna), [006-painel-custos](../../specs/006-painel-custos/spec.md) (consome a série)
**Altera**: `wiki/arquitetura_tecnica_desafio13_v2.md` (§4 — ERD)

---

## Contexto

A clarificação de 2026-07-14 da spec 001 resolveu a contradição "CSV com km × ERD sem km"
decidindo que a coluna `km` existiria **apenas no arquivo-fonte**: o pipeline a usaria para
atualizar `veiculo.km_atual` e a descartaria, mantendo o ERD da arquitetura v1 intacto.

A revisão cruzada das specs revelou o custo escondido dessa escolha: **sem persistir as
leituras de hodômetro, não existe série temporal de km no banco consolidado** —
`veiculo.km_atual` é um escalar sobrescrito a cada carga. A spec 006 (painel de custos)
promete **custo/km por período** como base do comparativo "candidato a renovação" (FR-002,
US2) e tem edge case explícito para "km rodado no período zero ou não confiável". Sem a
série, o km rodado num período não é calculável: restaria só o `km_no_momento` da manutenção
(esparso demais) ou um custo/km "de vida inteira" (custo total ÷ km_atual), incorreto para
veículos que não começaram do zero.

Na vida real, sistemas de gestão de abastecimento do setor público (GestCombustível,
Ticket Log, ValeCard/MaxiFrota) registram o **hodômetro em cada abastecimento** exatamente
por isso: é a fonte primária de km rodado e de consumo (km/L) da frota.

## Decisão

A tabela consolidada `ABASTECIMENTO` **ganha a coluna `km_hodometro` (int, nullable)** — a
leitura do odômetro no momento do abastecimento, vinda do CSV-fonte:

```text
ABASTECIMENTO (id, placa FK, data, litros, valor, km_hodometro, condutor_pseudo, fonte_origem)
```

- O pipeline (spec 003) continua atualizando `veiculo.km_atual` com a maior leitura válida —
  e agora também persiste a leitura no evento.
- `km_hodometro` é nullable: registro sem km continua válido para custos por período
  (a inconsistência "km ausente" segue existindo, tratada pelo motor como já previsto).
- Não há impacto LGPD: leitura de odômetro não é dado pessoal.
- A clarificação da spec 001 foi atualizada para refletir esta decisão (supersede o
  "não persiste o km na tabela consolidada").

## Alternativas consideradas

### Alternativa A: manter o descarte do km (decisão original da clarificação)

**Por que não foi escolhida**:
- Inviabiliza o custo/km por período da spec 006 — funcionalidade prometida no comparativo
  de renovação, argumento central do pitch;
- Joga fora informação que a fonte real oferece de graça e que o próprio CSV simulado já
  carrega.

**Vantagens** (não aproveitadas):
- ERD da arquitetura v1 intacto, sem necessidade de nova versão do documento.

### Alternativa B: tabela separada de leituras de hodômetro (`LEITURA_KM`)

Uma tabela dedicada consolidando leituras vindas de abastecimento **e** manutenção.

**Por que não foi escolhida**:
- Complexidade a mais (join adicional, mais uma tabela para carregar/testar) sem ganho na
  PoC — viola "simplicidade > sofisticação" (constitution VII);
- A leitura já tem casa natural no evento que a originou; a 006 agrega por SQL simples.

## Consequências

### Aceitas

- Custo/km por período torna-se calculável por consulta direta (max−min de `km_hodometro`
  no período, por placa);
- O consumo (km/L) por veículo vira indicador possível no painel de custos — reforça o
  comparativo de renovação;
- Coerência com a prática real dos sistemas de abastecimento de frota.

### Trade-offs

- ERD alterado → exige esta v2 da arquitetura + atualização da spec 002 pelo responsável
  (uma coluna a mais na migration);
- Leituras de hodômetro inconsistentes (ex.: decrescentes) agora ficam visíveis no
  consolidado — o que é desejável (motor já prevê `dados_insuficientes` para km não
  confiável), mas exige que o gerador (spec 001) produza séries monotônicas exceto nas
  anomalias propositais (ver ADR-003).

### Condições que invalidam esta decisão

Esta decisão deve ser **revisitada** se:

1. A fonte real de abastecimento da Prefeitura não fornecer hodômetro (aí a série viria só
   da manutenção e o custo/km por período teria que ser re-escopado);
2. O volume de dados tornar a série de leituras um problema de armazenamento (irrelevante
   na PoC).

### Caminho de migração

1. Se preciso reverter: dropar a coluna `km_hodometro` e re-escopar a 006 para custo/km de
   vida inteira — nenhuma outra tabela depende dela.

## Referências

- [GestCombustível — gestão de abastecimento no setor público (registra veículo, condutor, litros, valor e hodômetro)](https://gestcombustivel.com.br/)
- [Ticket Log — gestão de frotas e abastecimento](https://www.ticketlog.com.br/)
- [Manual do Gestor MaxiFrota — gestão de abastecimento (Governo do Paraná)](https://www.administracao.pr.gov.br/sites/default/arquivos_restritos/files/documento/2019-06/manual_gestor.pdf)
- Spec 006, FR-002 e edge case "custo por km": `specs/006-painel-custos/spec.md`
- ADRs relacionados: [ADR-001](ADR-001-placa-canonica-dois-formatos.md), [ADR-003](ADR-003-calibracao-realismo-fontes-simuladas.md)
