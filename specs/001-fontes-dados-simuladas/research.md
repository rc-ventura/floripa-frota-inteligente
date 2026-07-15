# Research — Fontes de Dados Simuladas (Spec 001)

**Branch**: `feature/001-fontes-dados-simuladas` | **Date**: 2026-07-14

Resolução dos unknowns técnicos e decisões de implementação para o gerador de dados.
Todas as ambiguidades funcionais foram resolvidas na sessão de clarificação (ver `spec.md`
§ Clarifications); este documento cobre as decisões de *como* implementar.

---

## R1. Estratégia de determinismo (FR-006, SC-004)

**Decisão**: Usar `numpy.random.default_rng(SEED)` com `SEED = 42` (constante no gerador) como
 único gerador de aleatoriedade. Todas as chamadas aleatórias (placas, datas, valores, km,
 seleção de veículos da demo) passam por este `Generator`. Nenhuma fonte de entropia externa
 (`os.urandom`, `datetime.now()` não-seedado, `random.random()` solto).

**Racional**: `numpy.random.default_rng` é o gerador moderno recomendado pelo NumPy (PCG64,
 determinístico, reproduzível cross-platform). Centralizar em um único `Generator` garante que
 a ordem das chamadas não afeta o resultado final de forma não-controlada — qualquer função
 que precise de aleatoriedade recebe o `rng` como argumento.

**Alternativas consideradas**:
- `random.seed(42)` + `random.*`: rejeitado — `random` do stdlib é global e frágil (qualquer
  biblioteca terceira que chame `random` desloca o estado).
- Múltiplos `default_rng` por fonte: rejeitado — mais difícil de rastrear a ordem; um único
  rng compartilhado é mais simples e igualmente determinístico.

**Verificação**: teste `test_determinismo` roda o gerador 2x em diretórios temporários e
 compara checksums SHA-256 de cada arquivo de saída → devem ser idênticos (SC-004).

---

## R2. Geração de CNH sintética não-real (clarificação CNH/AIT)

**Decisão** *(refinada em 2026-07-14 — ADR-003)*: Gerar `cnh` com 9 dígitos aleatórios,
 **calcular o dígito verificador correto (módulo 11) e perturbá-lo de propósito**
 (ex.: `dv_invalido = (dv_correto + 1) % 10`), totalizando 11 dígitos. O formato espelha o
 "Número do Registro Nacional" da CNH (Resolução CONTRAN 886/2021: 9 caracteres + 2 dígitos
 verificadores = 11), mas o checksum é **garantidamente** inválido — o número é obviamente
 sintético e não corresponde a nenhum condutor real.

 > Nota de refinamento: a decisão original ("11 dígitos aleatórios, sem calcular DV") deixava
 > ~1% das CNHs com DV válido por coincidência, contradizendo a promessa de "checksum
 > inválido". Perturbar o DV calculado garante 100% de invalidez estrutural.

**Racional**: A clarificação decidiu que o campo `cnh` espelha o Bloco 3 do AIT (Portaria
 SENATRAN 354/2022) para evidenciar que fontes reais carregam dado pessoal. O valor precisa
 *parecer* uma CNH (formato certo) mas ser *claramente não-real* (checksum inválido) — assim
 a varredura LGPD (SC-003) passa e a banca vê o desafio LGPD materializado na fonte. O
 pipeline (spec 003) descarta o campo na carga consolidada.

**Alternativas consideradas**:
- CNH com checksum válido (módulo 11): rejeitado — gerar números que passam na validação
  oficial cria risco de colidir com uma CNH real (mesmo que improvável); viola o espírito
  do princípio IV (constitution).
- String literal "CNH-SINTETICA-NNN": rejeitado — não espelha o formato real do AIT,
  enfraquece a evidência do desafio LGPD.

**Referência**: Resolução CONTRAN nº 886/2021, art. 4º, inciso I (Registro Nacional = 9 + 2
 dígitos).

---

## R3. Escrita de XLSX multi-abas (manutenção)

**Decisão**: Usar `pandas.ExcelWriter(path, engine="openpyxl")` e `df.to_excel(writer,
 sheet_name=...)` por aba. As abas representam setores/fontes diferentes dentro da planilha
 de manutenção (ex.: `Oficina Central`, `Oficina Regional Norte`, `Manutenção Terceirizada`),
 cada uma com a mesma estrutura de colunas mas com inconsistências de texto propositais em
 proporções diferentes.

**Racional**: `openpyxl` é a engine padrão do pandas para `.xlsx` e já está no ecossistema
 (decisão D1). Multi-abas espelha o cenário real "planilha do setor de manutenção" onde
 diferentes oficinas mantêm abas separadas com padrões inconsistentes — reforça a narrativa
 de heterogeneidade (princípio III da constitution). As colunas são o subconjunto mínimo
 dos campos presentes em planilhas reais de manutenção de frota (veículo, data, tipo,
 preventiva/corretiva, km no serviço, valor, oficina — ver R13); a aba codifica a oficina.

**Alternativas consideradas**:
- XLSX de aba única: rejeitado — a spec diz explicitamente "XLSX multi-abas" (FR-001, US1).
- `xlsxwriter`: rejeitado — não lê XLSX (só escreve); `openpyxl` lê e escreve, útil para
  testes que inspecionam o arquivo gerado.

---

## R4. Posicionamento determinístico dos 2 veículos da demo (FR-005)

**Decisão**: Os 2 veículos da demo são **sempre** os 2 primeiros veículos leves do cadastro
 (`veiculos.json` índices 0 e 1, fixos pela semente). O gerador os marca com um campo
 booleano `demo_gatilho: true` no cadastro interno. O posicionamento relativo aos limiares
 é calculado explicitamente, não aleatório:

- **Veículo A (gatilho km)**: última `troca_oleo` foi há X km tal que
  `km_desde_ultima = limite_km - 600 = 5000 - 600 = 4400`. Logo, faltam 600 km para o
  limite; o alerta de antecedência dispara a `limite_km - antecedencia_km = 4500`. O
  CSV-gatilho deposita um abastecimento cujo km/hodômetro eleva `km_atual` para ≥ 4501,
  cruzando o limiar de antecedência.
- **Veículo B (gatilho tempo)**: última `troca_oleo` foi há Y dias tal que
  `dias_desde_ultima = limite_dias - 20 = 180 - 20 = 160`. Logo, faltam 20 dias para o
  limite; o alerta dispara a `limite_dias - antecedencia_dias = 165`. O veículo B não
  precisa de gatilho de abastecimento — o alerta de tempo dispara sozinho quando o motor
  roda (a demo pode esperar o ciclo, ou o gerador pode plantar a data de forma que no dia
  da demo `dias_desde_ultima` já tenha cruzado 165).

  > **Refinamento da demo**: para garantir disparo *ao vivo* sem depender de esperar dias
  > reais, o veículo B nasce com `dias_desde_ultima = 164` (1 dia antes do limiar de
  > antecedência 165). O apresentador, na demo, **edita a data da última manutenção** via
  > painel (ou o gerador gera um CSV de "manutenção retroativa") para empurrar a data e
  > cruzar 165. Alternativa mais simples: o veículo B nasce com 166 dias (já cruzou) e o
  > alerta aparece no primeiro ciclo do motor na demo. **Decisão: veículo B nasce com
  > `dias_desde_ultima = 166`** (já cruzou o limiar de antecedência 165, mas não o limite
  > 180) — o alerta dispara no primeiro ciclo do motor, evidenciando o gatilho de tempo
  > sem depender de manipulação ao vivo. O veículo A é o gatilho ao vivo via CSV.

**Racional**: Posicionamento explícito (não aleatório) garante SC-004 trivialmente — os
 valores são literais, não dependem da semente. Os demais 38 veículos recebem
 `km_desde_ultima` e `dias_desde_ultima` aleatórios *dentro* dos limites (longe dos
 limiares), para não gerar alertas espúrios.

**Alternativas consideradas**:
- Posicionamento aleatório próximo ao limiar: rejeitado — frágil, pode acidentalmente
  cruzar o limiar e disparar alerta antes da demo.
- Veículo B dependendo de manipulação de data ao vivo: rejeitado — adiciona complexidade
  à demo e risco de falha (princípio I: demo-crítico primeiro, robustez).

---

## R5. Mini-API FastAPI das multas (FR-008, decisão D5)

**Decisão**: `fake_api/main.py` é uma app FastAPI mínima que lê `fake_api/multas.json` (gerado
 pelo `gerador_dados.py`) no startup e expõe:

- `GET /multas` → retorna lista JSON completa (todos os registros).
- `GET /multas/{placa}` → retorna lista filtrada por placa (conveniência para testes; a
  placa é comparada em minúsculas, espelhando o formato da fonte).
- `GET /health` → `{"status": "ok"}` (para o pipeline/scheduler verificar disponibilidade).

O JSON é carregado uma vez no startup (não relê a cada request). Sem banco, sem auth — é uma
 fonte simulada, não um serviço production-grade.

**Racional**: A decisão D5 escolheu FastAPI pela simplicidade (~20 linhas) e por demonstrar
 ingestão via HTTP real (não só arquivos). Carregar o JSON no startup evita I/O por request e
 mantém o endpoint sub-millisecond localmente. O `GET /multas/{placa}` é conveniência para
 testes do extrator (spec 003), não requisito da spec 001.

**Alternativas consideradas**:
- Flask: rejeitado (D5 já decidiu FastAPI).
- JSON estático servido por `python -m http.server`: rejeitado — não demonstra endpoint
  REST real, enfraquece a narrativa de "integração com sistema externo tipo DETRAN".
- FastAPI gerando as multas on-the-fly: rejeitado — viola o determinismo (a API seria
  outra fonte de aleatoriedade) e quebra o princípio de que o `gerador_dados.py` é a
  única fonte de verdade dos dados. A API só *serve* o que o gerador produziu.

**Como subir**: `uvicorn fake_api.main:app --reload --port 8000` (documentado em
 `fake_api/README.md`).

---

## R6. Geração do arquivo SQLite de licenciamento (Fonte 4)

**Decisão**: Usar `sqlite3` do stdlib (ou SQLAlchemy com URL `sqlite:///`) para criar
 `data/seeds/licenciamento.sqlite` com uma tabela `licenciamento` contendo os registros.
 O gerador apaga e recria o arquivo a cada execução (idempotente: mesma semente → mesmo
 conteúdo). Inconsistências propositais: placas duplicadas (mesmo veículo com 2 registros
 de vencimento, um atual um antigo) e vencimentos em formatos distintos (`dd/mm/aaaa` como
 TEXT, `aaaa-mm-dd` como TEXT, e serial Excel como INTEGER).

**Racional**: `sqlite3` stdlib não adiciona dependência; SQLite é o formato definido pela
 arquitetura §2 para esta fonte. Armazenar datas como TEXT em formatos mistos espelha o
 "banco legado" com esquema frouxo — evidência do risco de heterogeneidade.

**Alternativas consideradas**:
- SQLAlchemy para tudo: rejeitado nesta spec — SQLAlchemy é decisão da spec 002 (modelo
  consolidado); o gerador de fontes legadas deve usar o mínimo possível para espelhar
  "sistema legado que não foi modelado com cuidado". `sqlite3` stdlib basta.

---

## R7. Placas: formato canônico e grafias divergentes por fonte

**Decisão** *(atualizada em 2026-07-14 — ADR-001)*: O cadastro base (`veiculos.json`) carrega
 a placa canônica em **um dos dois formatos vigentes** (maiúsculas, sem hífen): ~70%
 Mercosul `AAA9A99` e ~30% antigo `AAA9999`, refletindo uma frota renovada gradualmente.
 A regex canônica única é `^[A-Z]{3}\d[A-Z\d]\d{2}$` (cobre ambos; a normalização do
 pipeline — upper + strip de hífen/espaço — não muda). Cada fonte aplica uma *transformação
 de grafia* determinística ao escrever seus registros, para produzir as inconsistências
 propositais:

| Fonte | Grafia da placa | Exemplo (canônico `ABC1234`) |
|---|---|---|
| Abastecimento (CSV) | Mistura: ~50% com hífen `ABC-1234`, ~50% sem hífen `ABC1234` | `ABC-1234` |
| Multas (JSON/API) | Minúsculas, sem hífen | `abc1234` |
| Manutenção (XLSX) | Maiúsculas, sem hífen (canônico) | `ABC1234` |
| Licenciamento (SQLite) | Maiúsculas, mas com duplicatas (mesma placa, 2 linhas) | `ABC1234` (×2) |

**Racional**: A placa é a chave de reconciliação (constitution II, arquitetura §2). As grafias
 divergentes são o input esperado do pipeline (spec 003 fará a normalização para o canônico
 dual — `AAA9999`/`AAA9A99`, ADR-001).
 Os 2 veículos da demo mantêm placas válidas no formato canônico nas fontes que usam
 maiúsculas (manutenção, licenciamento), mas também aparecem com hífen/minúsculas nas outras
 — isso NÃO os invalida, porque a normalização do pipeline os recuperará (Edge Case da spec:
 "as inconsistências não podem tornar um veículo da demo inválido" refere-se a rejeição por
 `placa_invalida`, não a grafia divergente que normaliza corretamente).

**Geração de placas**: todas únicas no cadastro, no formato sorteado para o veículo
 (Mercosul `AAA9A99` ou antigo `AAA9999`, proporção ~70/30). Série determinística via `rng`.

---

## R8. Documentação das inconsistências (FR-003)

**Decisão**: Gerar `data/seeds/INCONSISTENCIAS.md` como artefato versionado, listando cada
 inconsistência propositais por fonte, com exemplo concreto extraído dos dados gerados e
 referência à regra de qualidade que a trata (na spec 003). Este arquivo é a evidência
 verificável para SC-002 ("100% das inconsistências documentadas").

**Estrutura do arquivo**: tabela por fonte → inconsistência → exemplo → regra de tratamento
 (na spec 003) → motivo de rejeição esperado em `log_qualidade` (quando aplicável).

---

## R9. Dependências do projeto (pyproject.toml)

**Decisão**: Criar `pyproject.toml` na raiz (se não existir) com `uv` ou `poetry` como
 gestor. Dependências desta spec:

```
pandas>=2.2
openpyxl>=3.1
fastapi>=0.110
uvicorn>=0.30
numpy>=1.26
```

Dev-dependências: `pytest>=8.0`, `httpx>=0.27` (para testar o endpoint FastAPI com
 `TestClient`).

**Racional**: `uv` é mais rápido e moderno; `poetry` é mais estabelecido. Decisão final fica
 para `tasks.md` (fase de implementação) — este research recomenda `uv` por velocidade em
 ciclo de hackathon, mas ambas são aceitáveis. A versão mínima segue a regra de segurança
 (publicada há > 7 dias).

**Alternativas consideradas**:
- `requirements.txt` + `pip`: rejeitado — menos reprodutível que um lockfile gerenciado.
- Sem gestor (instalação manual): rejeitado — viola o princípio de reprodutibilidade e
  dificulta o `docker compose up` da spec 007.

---

## R10. Multas: gravidade → valor fixo do CTB (ADR-003)

**Decisão**: O gerador sorteia a **gravidade** da infração e deriva o `valor` da tabela do
 CTB: leve R$ 88,38 · média R$ 130,16 · grave R$ 195,23 · gravíssima R$ 293,47 (com
 multiplicadores ×2/×3 para uma pequena fração de gravíssimas agravadas). O JSON-fonte
 carrega também `gravidade` e `codigo_infracao` (espelhando os blocos do AIT — Portaria
 SENATRAN 354/2022); na carga consolidada o pipeline persiste apenas os campos do ERD
 (`placa`, `data`, `valor`, `condutor_pseudo`, `situacao`, `fonte_origem`) — campos extras
 da fonte são ignorados, mesmo padrão da CNH.

**Racional**: valores de multa são tabelados por lei; um float contínuo sorteado é
 imediatamente reconhecível como sintético-malfeito por qualquer avaliador que conheça os 4
 valores canônicos. Distribuição sugerida: ~45% média, ~30% leve, ~15% grave, ~10%
 gravíssima, **enviesada por veículo/condutor** (concentrada em poucos, incluindo o veículo
 caro do R12) — multas uniformes por toda a frota não existem na prática e a concentração
 alimenta a análise por condutor prevista em D8.

---

## R11. Licenciamento: vencimento pelo final da placa + estados para o semáforo (ADR-003)

**Decisão**: `vencimento` segue o calendário do DETRAN-SC pelo **último dígito da placa**
 (final 1 → 31/03 · final 2 → 30/04 · ... · final 9 → 30/11 · final 0 → 30/12, do ano de
 exercício). Sobre essa base, o gerador posiciona deterministicamente: **≥2 registros
 vencidos** (exercício anterior não renovado) e **≥2 vencendo em ≤7 dias** da data-âncora da
 demo — nenhum deles entre os 2 veículos do cenário de alertas de manutenção (para não
 poluir o gatilho ao vivo). Os formatos de escrita continuam propositalmente mistos
 (`dd/mm/aaaa` TEXT, `aaaa-mm-dd` TEXT, serial Excel INTEGER — R6).

**Racional**: vencimento desconectado do final da placa contradiz um calendário público que
 qualquer catarinense conhece; e a spec 005 precisa dos três estados do semáforo
 (ok/atenção/vencido) já na primeira carga — sem isso a tela inicial da demo nasce
 monocromática.

---

## R12. Modelo de consumo, hodômetro monotônico e veículo caro (ADR-003)

**Decisão**: A geração de abastecimentos deixa de sortear litros/km independentes e passa a
 derivar de um **modelo físico simples**, por tipo de veículo:

| Tipo | km/mês (faixa) | Consumo típico | Tanque | Abastecimentos/mês (≈) |
|---|---|---|---|---|
| leve | 1.000–2.000 | 8–14 km/L | ~45 L | 3–5 |
| ambulancia | 2.000–3.500 | 6–10 km/L | ~60 L | 6–9 |
| caminhao | 1.500–2.500 | 2–5 km/L | ~150 L | 4–6 |

 Fluxo: sorteia-se km/mês do veículo (fixo pela semente) → série de hodômetro **monotônica
 crescente** ao longo dos 8 meses → cada abastecimento registra a leitura corrente e litros
 compatíveis com o trecho rodado ÷ consumo do veículo. O `km_no_momento` das manutenções é
 interpolado da **mesma série** (consistência entre fontes). Anomalias propositais (ex.: km
 ausente no XLSX) são as únicas exceções e ficam listadas em `INCONSISTENCIAS.md`.
 Volumes resultantes: ~1.500 abastecimentos, ~300 manutenções, ~100 multas.

 **Veículo caro (FR-009)**: um veículo leve (fora dos 2 da demo) nasce com
 `custo_desproporcional: true`: consumo no piso da faixa (≈8 km/L), 2–3 manutenções
 corretivas extras de valor alto e a maior concentração de multas — o suficiente para o
 comparativo da spec 006 destacá-lo por custo/km muito acima da mediana da categoria.

**Racional**: o painel de custos (spec 006) expõe derivações que a banca verifica de cabeça
 (custo/km, km/L). Sorteios independentes produziam ~75 abastecimentos/veículo com consumo
 implícito de 2–5 km/L em carro leve — fisicamente absurdo. O modelo mantém o gerador
 simples (3 faixas paramétricas) e torna SC-005 testável por asserção direta.

**Alternativas consideradas**:
- Sorteios independentes por campo: rejeitado — consumo derivado absurdo (ver acima).
- Fidelidade estatística completa (sazonalidade, distribuições reais): rejeitado —
  complexidade sem valor de demo (constitution VII).

---

## R13. Manutenção realista: categoria, catálogo de marcas, garantia e revisões programadas (ADR-003 itens 7–9)

**Decisão** *(2026-07-15)*: quatro regras adicionais para a Fonte 3 e o cadastro:

1. **Coluna `categoria`** no XLSX (`preventiva` | `corretiva`, com grafias variadas:
   "Preventiva", "CORRETIVA", "prev."), **persistida** na MANUTENCAO consolidada
   (arquitetura v2 §4). O gerador calibra o valor das corretivas a **3–5× o valor médio
   das preventivas** do mesmo tipo de veículo, concentrando-as no veículo
   `custo_desproporcional` — assim o painel de custos demonstra o benchmark do pitch
   (spec 007: "corretiva custa 3–5× a preventiva") nos próprios dados.
2. **Catálogo de marcas/modelos por tipo**, observado em frotas municipais reais:
   - leves: Fiat Strada, Chevrolet Onix, Chevrolet Spin, Chevrolet Montana, VW Gol,
     VW Saveiro, Renault Kwid;
   - ambulâncias: Renault Master, Fiat Ducato;
   - caminhões: VW Delivery, Mercedes-Benz Accelo.
   O gerador sorteia deterministicamente do catálogo; `ano` distribuído ~2015–2026.
3. **Garantia e revisões programadas**: veículos com `ano ≥ 2023` recebem
   `em_garantia: true` (~25% da frota; garantia típica de 3 anos). Para eles, as
   manutenções aparecem como **revisões programadas nos marcos do fabricante**
   (10.000 km ou 12 meses, o que vier primeiro): grafias "Revisão 10.000 km",
   "REVISAO 20000", "revisão dos 30 mil" na aba `Manutenção Terceirizada`
   (concessionária), normalizadas pelo pipeline para `revisao_geral`. Veículos fora de
   garantia têm manutenção itemizada (troca_oleo, filtros, pneus) nas oficinas próprias.
   **O motor de alertas não muda**: garantia afeta onde/como o evento aparece na fonte,
   não a lógica de limiares.
4. **`revisao_geral` leve/ambulância = 10.000 km/365 dias** na tabela-semente (era
   20.000): alinha ao plano padrão de fabricante; caminhões permanecem 30.000 km.

**Racional**: planilhas reais de manutenção sempre trazem preventiva×corretiva, nº de OS,
 km e oficina — nossas colunas são o subconjunto mínimo, e `categoria` era a ausência de
 maior valor (habilita o benchmark do pitch). Marcas/modelos do catálogo aparecem em
 licitações e leilões de prefeituras reais. Limiares permanecem **por tipo de veículo**
 (briefing 4.3); plano por modelo fica como evolução via coluna adicional em
 `LIMIAR_CONFIG` com regra "mais específico vence" (dados, não código — constitution V).

**Alternativas consideradas**:
- Limiar por marca/modelo na PoC: rejeitado — os planos das marcas populares convergem
  (10.000 km/12 meses); a tabela teria linhas quase idênticas (constitution VII).
- Aba própria "Concessionária" no XLSX: rejeitado — a aba `Manutenção Terceirizada` já
  cobre o cenário sem mudar o contrato de 3 abas.
- Campos administrativos completos (nº OS, empenho, peças × mão de obra): rejeitado na
  PoC — não alimentam motor nem painel; documentados como staging futuro numa
  integração real.

**Referências**: ver ADR-003 (adendo 2026-07-15) — planilhas de manutenção (Produttivo,
 Cobli, Guia do Excel), revisão programada Fiat, garantia condicionada (AutoPapo), frota
 municipal de Itaí-SP e leilões de prefeitura.
