# ADR-003: Calibração de realismo das fontes simuladas (gerador de dados — spec 001)

**Status**: Proposta — ratifica com o merge deste MR em `dev`
**Data**: 2026-07-14 · **Adendo**: 2026-07-15 (itens 7–9 — realismo da fonte de manutenção)
**Spec relacionada**: [001-fontes-dados-simuladas](../../specs/001-fontes-dados-simuladas/spec.md)
**Escopo**: decisões de *geração* de dados; complementam ADR-001 e ADR-002. Exceção: o item 7 adiciona a coluna `categoria` à MANUTENCAO consolidada (refletida na arquitetura v2 §4)

---

## Contexto

A revisão da spec 001 contra referências reais (estrutura do Auto de Infração, calendário de
licenciamento do DETRAN-SC, intervalos de manutenção, sistemas de abastecimento de frota)
encontrou pontos em que dados sorteados de forma independente produziriam valores que um
avaliador atento reconheceria como impossíveis — e duas lacunas em que outras specs assumem
dados que a 001 não prometia gerar (veículo deliberadamente caro para a 006; estados
"atenção/vencido" para o semáforo da 005).

O objetivo da PoC não é fidelidade estatística, mas os números que a banca **consegue
verificar de cabeça** (valor de multa, vencimento de licenciamento, consumo km/L) precisam
ser plausíveis — o painel de custos expõe essas derivações diretamente.

## Decisão

O gerador (spec 001) adota as seguintes regras de calibração, todas encodadas como
clarificações/requisitos na spec:

1. **Multas com valores reais do CTB**: `valor` deixa de ser float sorteado e passa a derivar
   da gravidade sorteada — leve R$ 88,38 · média R$ 130,16 · grave R$ 195,23 · gravíssima
   R$ 293,47 (e multiplicadores ×2/×3 para gravíssimas agravadas). O JSON-fonte ganha campos
   `gravidade` e `codigo_infracao` (espelhando o AIT — Portaria SENATRAN 354/2022); a tabela
   consolidada `MULTA` permanece conforme o ERD (campos extras da fonte são ignorados na
   carga, mesmo padrão da CNH sintética).
2. **Licenciamento segue o final da placa**: `vencimento` respeita o calendário do DETRAN-SC
   (final 1 → 31/03 ... final 0 → 30/12), com `exercicio` implícito no ano. Alguns registros
   nascem **vencidos** (≥2) e **vencendo em ≤7 dias** (≥2) para o semáforo da spec 005 ter os
   três estados (ok/atenção/vencido) sem interferir no cenário determinístico de alertas.
3. **Modelo de consumo coerente** (em vez de sorteios independentes): km/mês por tipo de
   veículo → litros derivados do consumo típico (leve ~8–14 km/L; ambulância ~6–10 km/L;
   caminhão ~2–5 km/L) → frequência de abastecimento derivada do tanque. O **hodômetro é
   monotônico crescente** por veículo e consistente entre CSV de abastecimento e XLSX de
   manutenção — exceto nas anomalias propositais, que são listadas em `INCONSISTENCIAS.md`.
4. **Um veículo deliberadamente caro**: um veículo leve nasce com custo/km desproporcional
   (mais corretivas + consumo alto + multas concentradas), atendendo a assumption da spec
   006 (comparativo "candidato a renovação"). Multas são concentradas em poucos
   veículos/condutores (distribuição enviesada, não uniforme), o que também alimenta a
   análise por condutor prevista em D8.
5. **CNH sintética com DV propositalmente inválido**: em vez de 11 dígitos aleatórios (~1%
   dos quais teriam dígito verificador válido por acaso), o gerador calcula o DV correto e o
   **perturba** — garantindo 100% de CNHs estruturalmente inválidas, como promete a
   clarificação LGPD.
6. **Limiar `troca_oleo` leve = 5.000 km/180 dias fica, com justificativa registrada**:
   carros pós-2015 com óleo sintético usam 10.000 km/12 meses, mas frota municipal urbana é
   o caso clássico de **uso severo** (anda-e-para), para o qual a recomendação segue
   5.000 km/6 meses. A justificativa evita que o valor pareça desatualizado; os valores
   seguem parametrizados em `LIMIAR_CONFIG` (constitution V) — a spec 002 deve alinhar sua
   assumption (que citava ~10.000 km) a esta tabela.
7. **Manutenção com `categoria` preventiva × corretiva** *(adendo 2026-07-15)*: toda
   planilha real de manutenção de frota distingue preventiva de corretiva; a coluna entra
   no XLSX-fonte (com grafias variadas, como o `tipo`) **e é persistida** na MANUTENCAO
   consolidada (arquitetura v2 §4). Razão: o benchmark central do pitch (spec 007) é
   "corretiva custa 3–5× a preventiva" — com a categoria no consolidado, o painel de custos
   demonstra essa razão **nos próprios dados** (o gerador calibra corretivas a 3–5× o valor
   médio das preventivas, concentradas no veículo caro do item 4).
8. **Catálogo de marcas/modelos reais + garantia com revisões programadas** *(adendo
   2026-07-15)*: o cadastro sorteia de um catálogo por tipo observado em frotas municipais
   reais (leves: Fiat Strada, Chevrolet Onix/Spin/Montana, VW Gol/Saveiro, Renault Kwid;
   ambulâncias: Renault Master, Fiat Ducato; caminhões: VW Delivery, Mercedes Accelo), com
   `ano` distribuído ~2015–2026 e **~25% da frota em garantia** (`ano ≥ 2023`, garantia
   típica de 3 anos). Veículos em garantia registram **revisões programadas nos marcos do
   fabricante** (10.000 km ou 12 meses, o que vier primeiro), com grafias como
   "Revisão 10.000 km" na aba de manutenção terceirizada/concessionária — normalizadas
   pelo pipeline para `revisao_geral`. O motor de alertas **não muda**: garantia afeta onde
   e como o evento aparece na fonte, não a lógica de limiares.
9. **`revisao_geral` de leve e ambulância alinhada a 10.000 km/365 dias** *(adendo
   2026-07-15)*: a tabela-semente usava 20.000 km; o plano padrão de fabricante para flex e
   furgões diesel leves é 10.000 km/12 meses. O componente de tempo (365 dias) já batia; o
   de km foi alinhado. Caminhões permanecem 30.000 km (intervalos maiores em diesel pesado).
   Evolução documentada: planos por **modelo** entram, quando necessário, como coluna
   adicional em `LIMIAR_CONFIG` com regra "mais específico vence" — mudança de dados, não
   de código (constitution V).
10. **A anomalia de km-ausente nunca recai sobre a âncora** *(adendo 2026-07-15b — correção
    do ciclo 1 do sdd-final-review)*: além das âncoras da demo e dos marcos de garantia, o
    **evento de maior km de cada (placa, tipo de manutenção)** é imune ao km ausente. É esse
    evento que o motor usa em `km_desde_ultima`; anulá-lo faria o cálculo cair num evento
    anterior e cruzar o limiar de antecedência, gerando alertas espúrios em veículos
    não-demo — violação do invariante "demais veículos longe dos limiares" (bug HIGH
    confirmado por QA + Devin + Tech Leader no ciclo 1). Regressão coberta por
    `test_sem_alertas_espurios` (falhava antes do fix; passa depois).

Volumes recalibrados pelo modelo de consumo (plan da spec 001): ~1.500 abastecimentos,
~300 manutenções e ~100 multas em 8 meses × 40 veículos.

## Alternativas consideradas

### Alternativa A: sorteios independentes por campo (abordagem original do plan)

**Por que não foi escolhida**:
- Produz derivações absurdas visíveis no painel de custos (ex.: 75 abastecimentos/veículo
  com litros soltos ⇒ consumo de 2–5 km/L em carro leve);
- Valores de multa contínuos não existem no CTB — qualquer avaliador que conheça os 4
  valores canônicos nota;
- Vencimentos de licenciamento desconectados do final da placa contradizem o calendário
  público do DETRAN-SC.

**Vantagens** (não aproveitadas):
- Gerador marginalmente mais simples.

### Alternativa B: fidelidade estatística completa (distribuições reais por categoria, sazonalidade)

**Por que não foi escolhida**:
- Complexidade sem valor de demo (constitution VII); a banca verifica plausibilidade, não
  aderência estatística.

## Consequências

### Aceitas

- Indicadores derivados (custo/km, km/L, calendário de vencimentos) resistem à inspeção da
  banca; o cenário determinístico da demo permanece intacto (posicionamento explícito dos 2
  veículos, ADR não altera R4 do research).

### Trade-offs

- O gerador ganha um pequeno modelo físico (km/mês → litros → frequência) em vez de sorteios
  diretos — complexidade justificada registrada aqui (constitution VII).
- Mais invariantes para testar (monotonicidade do hodômetro, faixas de consumo, valores de
  multa ∈ tabela CTB) — viram testes de aceitação da spec 001.

### Condições que invalidam esta decisão

1. Alteração dos valores de multa do CTB ou do calendário DETRAN-SC (basta atualizar as
   constantes de geração — são dados de *fonte simulada*, não regra de negócio do motor);
2. Surgimento de amostra real da Prefeitura (os dados reais substituem a calibração).

## Referências

- [Anexo da Portaria SENATRAN 354/2022 — campos do Auto de Infração de Trânsito](https://www.gov.br/transportes/pt-br/assuntos/transito/arquivos-senatran/portarias/2022/Portaria3542022ANEXO.pdf)
- [CTB Digital — art. 280 (requisitos do AIT)](https://ctbdigital.com.br/artigo/art280/)
- [Autoescola Online — tipificação e valores por gravidade das infrações](https://www.autoescolaonline.net/tipificacao-da-infracao-de-transito/)
- [DETRAN-SC — licenciamento anual de veículos](https://www.detran.sc.gov.br/licenciamento-anual-veiculos/)
- [AutoPapo — calendário de licenciamento SC 2026 por final de placa](https://autopapo.com.br/noticia/licenciamento-sc-calendario-2026-detran-crlv/)
- [AutoPapo (Blog do Boris) — troca de óleo: 5 mil ou 10 mil km, 6 ou 12 meses](https://autopapo.com.br/blog-do-boris/trocar-o-oleo-motor-saiba-prazo-correto/)
- [Teclub — intervalo de troca de óleo: 5.000 km ainda faz sentido? (uso severo)](https://www.teclub.com.br/post/intervalo-troca-de-oleo-5-mil-km)
- [CARFAQ — guia de troca de óleo por quilometragem (2026)](https://carfaq.com.br/troca-de-oleo-a-cada-quantos-km/)
- [GestCombustível — campos registrados por abastecimento no setor público](https://gestcombustivel.com.br/)
- **Adendo 2026-07-15 (fonte de manutenção)**:
  - [Produttivo — planilha de manutenção de veículos (campos típicos: OS, preventiva/corretiva, km, valor, oficina)](https://www.produttivo.com.br/blog/planilha-de-manutencao-de-veiculos/)
  - [Cobli — controle de manutenção da frota + planilha](https://www.cobli.co/blog/controle-de-manutencao-da-frota/)
  - [Guia do Excel — planilha de controle de manutenção de veículos](https://www.guiadoexcel.com.br/planilha-excel-de-controle-de-manutencao-de-veiculos-2-0/)
  - [Fiat — revisão programada com preços fixos tabelados](https://servicos.fiat.com.br/revisao.html)
  - [AutoPapo (Blog do Boris) — garantia condicionada às revisões em dia](https://autopapo.com.br/blog-do-boris/perder-a-garantia-concessionaria-revisao/)
  - [Prefeitura de Itaí-SP — composição real de frota municipal (Master ambulância, Montana, Kwid, caminhões)](https://www.itai.sp.gov.br/licitacao/download/1368/)
  - [Leilão de prefeitura — Strada, Spin, Saveiro, Gol, caminhões (modelos típicos de frota municipal)](https://leilaodescomplicado.com/leilao-de-prefeitura-tem-fiat-strada-chevrolet-d20-spin-volkswagen-saveiro-gol-caminhoes-e-outros-equipamentos/)
- ADRs relacionados: [ADR-001](ADR-001-placa-canonica-dois-formatos.md), [ADR-002](ADR-002-persistir-km-hodometro-abastecimento.md)
