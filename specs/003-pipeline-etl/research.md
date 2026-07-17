# Research — Pipeline ETL de Integração das Fontes (Spec 003)

**Branch**: `feature/003-pipeline-etl` | **Date**: 2026-07-17

Decisões técnicas da Phase 0. Cada uma resolve um "como" que a spec deixa em aberto,
respeitando a constitution v1.0.1, o contrato do esquema (spec 002,
`contracts/esquema_tabelas.md`) e os contratos das fontes (spec 001).

---

## R1 — Detecção de novidade por hash de conteúdo, sem tabela de controle

**Decision**: cada extrator calcula o SHA-256 do conteúdo da fonte (arquivo CSV/XLSX/SQLite;
corpo da resposta JSON da API) e grava no staging `fonte_origem` no formato
`<identificador>@sha256:<12 primeiros hex>` (ex.: `abastecimento.csv@sha256:3fa9c01b22de`,
`http://localhost:8000/multas@sha256:9c1d44aa07b1`). Antes de extrair, consulta o próprio
staging (`SELECT 1 FROM stg_x WHERE fonte_origem LIKE '%@sha256:<hash>'`); hash já visto →
fonte pulada no ciclo (nada a extrair). O estado de "já visto" é 100% derivado do banco.

**Rationale**:
- Resolve os dois edge cases da spec de uma vez: arquivo re-depositado **ou renomeado** com o
  mesmo conteúdo tem o mesmo hash → não re-extrai, não duplica (US3.2).
- Mantém a assumption da spec: arquivos permanecem na pasta; o controle é do pipeline.
- Staging não explode no ciclo de 1–2 min da demo: fontes paradas → zero linhas novas por
  ciclo (as 4 fontes quase nunca mudam entre ciclos).
- Fortalece a rastreabilidade (constitution II): a carga identifica exatamente **qual
  conteúdo** entrou, não só o nome do arquivo.
- Zero estado fora do banco (constitution VI) e zero tabela nova (o esquema da spec 002 fica
  intacto — sem migration neste MR).

**Alternatives considered**:
- *Mover/renomear arquivo processado* — rejeitado: contradiz a assumption da spec ("arquivos
  permanecem na pasta") e quebraria o roteiro da demo (depositar 1 CSV e vê-lo processado).
- *Tabela de controle `arquivo_processado`* — rejeitado: exige migration + mudança do
  contrato 002 (que enumera o que o pipeline escreve) sem ganho funcional a este volume.
- *Re-extrair tudo a cada ciclo e confiar no upsert* — rejeitado: staging cresceria ~2.400
  linhas/ciclo (a cada 1–2 min) e o carimbo de carga viraria ruído de auditoria.

## R2 — Transform processa apenas o lote da carga corrente

**Decision**: cada ciclo marca suas inserções de staging com um `carga_em` único por
fonte/ciclo (timestamp do início da extração). O Validate & Transform lê **somente** os
registros desse lote (`WHERE carga_em = :lote`), nunca o staging inteiro.

**Rationale**:
- Idempotência de ponta a ponta observável: ciclo sem dados novos → transform sem entrada →
  zero upserts **e zero linhas novas em `log_qualidade`**. Sem isso, cada execução
  re-rejeitaria os mesmos inválidos históricos e o log cresceria a cada ciclo — rejeição
  duplicada é ruído que contamina a evidência para a banca (SC-002).
- O edge case "reprocessar staging antigo não pode reintroduzir duplicatas" continua coberto
  em profundidade: mesmo que um lote antigo seja reprocessado manualmente, as chaves UNIQUE
  do banco (contrato 002/ADR-004) tornam o upsert um no-op.

**Alternatives considered**:
- *Transformar o staging inteiro a cada ciclo* — rejeitado: log_qualidade cresceria a cada
  execução sobre os mesmos dados, violando o espírito de SC-001 ("mesmo estado") e sujando a
  trilha de auditoria.
- *Deletar staging após transformar* — rejeitado: staging é a trilha bruta de auditoria
  (constitution II); expurgo é política documentada via `carga_em`, não efeito colateral.

## R3 — Upsert por dialeto com `ON CONFLICT`; duplicata é intra-lote

**Decision**: a carga usa o construtor de INSERT do dialeto ativo
(`sqlalchemy.dialects.sqlite.insert` / `postgresql.insert`, selecionado por
`engine.dialect.name`):
- **Tabelas-fato** (`abastecimento`, `manutencao`, `multa`): `on_conflict_do_nothing()`
  **sem alvo explícito** — captura qualquer violação de UNIQUE, incluindo o índice de
  expressão `ux_multa_upsert` (que não é endereçável como lista de colunas).
- **Tabelas-dimensão** (`veiculo`, `licenciamento`): `on_conflict_do_update()` com alvo
  `placa`, atualizando os campos mutáveis (cadastro; `vencimento`/`situacao`).

A deduplicação **intra-lote** (2 registros idênticos na mesma carga — ex.: linhas duplicadas
do SQLite de licenciamento, multas idênticas no mesmo payload) acontece no transform, e é a
2ª ocorrência que vai a `log_qualidade` com motivo `duplicado`. Conflito **entre ciclos**
(registro já consolidado reaparecendo) é idempotência — no-op silencioso, não é rejeição
nem vai ao log.

**Rationale**:
- É exatamente a semântica prometida pelo contrato 002: "a 2ª duplicata vai para
  `log_qualidade`" refere-se à duplicata real no dado de entrada; re-execução sobre dados já
  vistos produz "mesmo estado" (SC-001), o que inclui o log (R2).
- `do_nothing` sem alvo evita acoplar o código à expressão `coalesce(condutor_pseudo, '')`
  do índice (ADR-004) — o banco decide o conflito, o pipeline não reimplementa a chave.
- A exceção deliberada de `abastecimento` (km NULL não colide — caminho 2 do ADR-004) é
  respeitada: a dedup fina desses casos é do transform (chave de lote
  `placa+data+km`, com km NULL tratado como valor distinto por linha — dois abastecimentos
  sem km no mesmo dia são eventos reais e ambos entram, conforme R7 da spec 002).

**Alternatives considered**:
- *`on_conflict_do_update` nas fatos* — rejeitado: fatos são imutáveis na PoC; update em
  conflito mascararia divergência de fonte (mesma chave, valores diferentes) que hoje é
  detectável no staging.
- *SELECT prévio das chaves + INSERT condicional* — rejeitado: duas idas ao banco, sujeito a
  corrida, e reimplementa em Python o que o UNIQUE já garante por construção (lição do
  research R7 da spec 002).

## R4 — Cadastro `veiculo` carregado de `data/seeds/veiculos.json`, sem staging

**Decision**: o ciclo carrega o cadastro canônico de veículos direto de
`data/seeds/veiculos.json` (upsert por `placa`, `fonte_origem =
data/seeds/veiculos.json@sha256:<hash>`, pulado por hash como as demais — R1), **antes** das
4 fontes de eventos (FK). Evento cuja placa normalizada não existe no cadastro é rejeitado
com motivo `veiculo_desconhecido` — atende o edge case "placa que não existe no cadastro:
rejeição com motivo próprio".

**Rationale**:
- O esquema exige: todas as tabelas de evento têm FK para `veiculo.placa`, e `tipo_veiculo`
  é NOT NULL — nenhuma das 4 fontes legadas carrega o tipo do veículo; só o cadastro tem.
  Sem cadastro primeiro, nenhum evento entra.
- `veiculos.json` simula o sistema patrimonial da Prefeitura (a referência interna da spec
  001); é dado já canônico e limpo — passá-lo por staging de "dado bruto sujo" seria teatro,
  e criar `stg_veiculo` mudaria o esquema/contrato da spec 002 sem ganho.
- A rastreabilidade se mantém: `fonte_origem` na consolidada aponta arquivo + hash
  (constitution II é sobre origem rastreável; staging é obrigatório para registro **de
  staging**, não uma passagem obrigatória universal).

**Alternatives considered**:
- *Cadastro emergindo das fontes de evento* (visão original "o cadastro emerge na
  reconciliação") — rejeitado: obrigaria a inventar `tipo_veiculo` (default silencioso —
  viola constitution III) e quebraria o motor (limiar é por tipo de veículo).
- *Criar `stg_veiculo` + migration* — rejeitado: fora do escopo da spec (esquema é da 002);
  benefício nulo para dado que nasce canônico.

## R5 — Parsing tolerante de datas: 3 formatos, ordem fixa, sem fuzzy

**Decision**: função única `interpretar_data(valor) -> date | None` tentando, na ordem:
(1) `dd/mm/aaaa` (`datetime.strptime`), (2) `aaaa-mm-dd` (ISO), (3) serial Excel — inteiro
na faixa 20.000–80.000 (≈1954–2119), convertido com origem `1899-12-30`. Vazio/None →
rejeição `data_ausente`; não interpretável (incluindo data inexistente como `31/02/2026`) →
`data_invalida`.

**Rationale**: cobre exatamente os formatos catalogados nos contratos da spec 001
(abastecimento: 2 formatos texto; manutenção e licenciamento: texto + serial). Ordem fixa e
determinística evita ambiguidade — `dd/mm` testado antes de ISO porque `strptime` com
`%d/%m/%Y` não aceita ISO e vice-versa (formatos mutuamente exclusivos, sem falso positivo).

**Alternatives considered**:
- *`dateutil.parser` fuzzy* — rejeitado: aceita lixo com falso positivo (ex.: interpreta
  `13/25/99` "criativamente"); dependência nova; comportamento não determinístico entre
  versões.
- *`pandas.to_datetime` com `errors='coerce'` direto no DataFrame* — rejeitado como parser
  único: mistura os formatos por coluna inteira (dayfirst global) e mascara qual linha
  falhou por qual motivo — perderíamos o motivo granular exigido por FR-005.

## R6 — Vocabulários por normalização + tabela de mapeamento no transform

**Decision**: normalização textual (casefold, remoção de acentos via `unicodedata`, colapso
de espaços/pontuação) seguida de mapeamento explícito:
- `tipo` de manutenção: contém `oleo` → `troca_oleo`; contém `filtro` → `filtros`; contém
  `pneu` → `pneus`; contém `revisao` (inclusive `revisao 10000`, `Revisão 10.000 km`) →
  `revisao_geral`. Sem correspondência → rejeição `tipo_desconhecido`.
- `categoria`: prefixo `prev` → `preventiva`; prefixo `corr` → `corretiva`. Sem
  correspondência → rejeição `categoria_desconhecida`.
- `situacao` (multas/licenciamento): já padronizadas na fonte (contratos 001); valor fora do
  CHECK do banco → rejeição `situacao_desconhecida` (defesa em profundidade, não esperado).

**Rationale**: cobre todas as grafias catalogadas em `data/seeds/INCONSISTENCIAS.md`
(`FILTROS`, `REVISAO 60000`, `prev.`, `Troca Óleo`...). Mapeamento por radical é resiliente a
grafia nova do mesmo conceito (constitution III) sem virar adivinhação — conceito realmente
novo é rejeitado com motivo e vira regra nova + documentação (assumption da spec). Não é
constante de negócio (constitution V): é regra de qualidade dado→dado, versionada e
documentada no `pipeline/README.md` (FR-009).

**Alternatives considered**:
- *Igualdade exata com lista fechada de grafias* — rejeitado: qualquer variação nova
  (`REVISAO 40000`) viraria rejeição, gerando ruído para um conceito já conhecido.
- *Fuzzy matching (Levenshtein)* — rejeitado: complexidade sem requisito (constitution VII)
  e risco de mapear errado silenciosamente.

## R7 — Vocabulário fechado de motivos de rejeição (este MR)

**Decision**: motivos em snake_case gravados em `log_qualidade.motivo_rejeicao`, fixados no
contrato (`contracts/ciclo_pipeline.md`):

| Motivo | Gatilho |
|---|---|
| `placa_invalida` | placa não normalizável para o canônico ADR-001 (inclui ausente/vazia) |
| `data_ausente` | campo de data vazio/None |
| `data_invalida` | data presente mas não interpretável pelos 3 formatos (R5) |
| `valor_invalido` | litros/valor/km não conversível para numérico |
| `tipo_desconhecido` | tipo de manutenção fora do mapeamento (R6) |
| `categoria_desconhecida` | categoria fora de preventiva/corretiva (R6) |
| `situacao_desconhecida` | situação fora do CHECK (defesa em profundidade) |
| `duplicado` | 2ª ocorrência da chave natural no mesmo lote (R3) |
| `veiculo_desconhecido` | placa canônica válida, mas ausente do cadastro (R4) |
| `fonte_indisponivel` | falha da fonte inteira no ciclo (R8) — registro é a descrição do erro |

**Rationale**: SC-002 exige 100% dos inválidos com motivo; um vocabulário fechado e
versionado é o que permite ao teste (e à banca) verificar a cobertura. Estende os 3 motivos
exemplificados na constitution II sem contradizê-los. Motivo novo = atualização do contrato
no mesmo MR (regra de estabilidade herdada da spec 002).

## R8 — Falha de fonte: try/except por extrator + registro em `log_qualidade`

**Decision**: `executar_ciclo()` envolve cada fonte em try/except individual. Exceção da
fonte (API fora, arquivo corrompido/ilegível, SQLite ausente) → grava em `log_qualidade`
(`fonte` = identificador da fonte, `registro_bruto` = classe + mensagem do erro,
`motivo_rejeicao = fonte_indisponivel`, `carga_em` = timestamp do ciclo) + `logging.error`,
e o ciclo segue para a próxima fonte. Linha corrompida **dentro** de arquivo legível não é
falha de fonte: é rejeição de registro (motivos R7), e o resto do lote segue (edge case
"parcialmente corrompido").

**Rationale**: SC-005/US4 pedem que a falha "fique registrada para diagnóstico" — reusar
`log_qualidade` mantém o diagnóstico no banco (visível a painéis/auditoria, constitution VI:
camadas conversam via banco) sem criar tabela nova. A distinção fonte-inteira × linha
mantém o tudo-ou-nada proibido pela spec.

**Alternatives considered**:
- *Tabela `log_execucao` própria* — rejeitado: migration fora de escopo; `log_qualidade`
  tem exatamente os campos necessários.
- *Apenas `logging` em arquivo/console* — rejeitado: invisível para as camadas superiores e
  perdível no container da demo; viola "fica registrada".

## R9 — Cliente HTTP do extrator de multas: `httpx` promovida a dependência principal

**Decision**: `httpx>=0.27` sai do grupo `dev` e entra em `dependencies`; o extrator usa
`httpx.get(f"{MULTAS_API_URL}/multas", timeout=5.0)` com verificação prévia opcional de
`/health`. Timeout curto: fonte lenta = fonte indisponível no ciclo (R8), sem segurar as
demais.

**Rationale**: já está no lockfile (usada nos testes da spec 001) — custo zero de cadeia de
dependências; timeouts e erros explícitos melhores que `urllib` stdlib; o contrato da API
(spec 001) já documenta o `500` como caso a tratar.

**Alternatives considered**:
- *`urllib.request` (stdlib)* — rejeitado: ergonomia pobre de timeout/erros; economia de
  dependência que o lockfile já pagou.
- *`requests`* — rejeitado: dependência nova redundante com httpx já presente.

## R10 — `veiculo.km_atual`: recalculado da série consolidada após a carga

**Decision**: após o upsert de abastecimento, para cada placa afetada no lote:
`UPDATE veiculo SET km_atual = (SELECT MAX(km_hodometro) FROM abastecimento WHERE placa = :p
AND km_hodometro IS NOT NULL)` quando esse MAX superar o `km_atual` corrente (guarda de
monotonicidade — km nunca regride por carga fora de ordem). SQL portável SQLite/Postgres
(sem `GREATEST`, que o SQLite não tem).

**Rationale**: implementa FR-010/ADR-002 ("maior leitura válida da placa") de forma
idempotente por construção — recalcular do consolidado dá o mesmo resultado em N execuções,
independente da ordem de chegada dos arquivos. Leitura decrescente não rejeita o registro
(entra no consolidado como fato; confiabilidade é juízo do motor — spec 004), apenas não
rebaixa `km_atual`.

**Alternatives considered**:
- *Acumular max em Python durante o transform* — rejeitado: correto só se o lote for a única
  fonte de verdade; o recálculo do consolidado é imune a reprocessamento parcial.
- *Trigger no banco* — rejeitado: lógica de pipeline no storage dificulta teste e viola a
  separação de papéis do contrato 002 (o pipeline atualiza `km_atual`).

---

## Resumo das pendências da spec

Nenhum NEEDS CLARIFICATION restante: origem do cadastro (R4), estado de "já visto" (R1),
semântica de duplicata × idempotência (R2/R3), formatos de data (R5), vocabulários (R6),
motivos (R7), falha de fonte (R8), cliente HTTP (R9) e km_atual (R10) estão decididos.
