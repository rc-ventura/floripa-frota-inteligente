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

**Decisão**: Gerar `cnh` como string de 11 dígitos numéricos aleatórios
 (`f"{rng.integers(0, 10**11):011d}"`), **sem cálculo de dígito verificador válido**.
 O formato espelha o "Número do Registro Nacional" da CNH (Resolução CONTRAN 886/2021: 9
 caracteres + 2 dígitos verificadores = 11), mas como o checksum é inválido, o número é
 obviamente sintético e não corresponde a nenhum condutor real.

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
 de heterogeneidade (princípio III da constitution).

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

**Decisão**: O cadastro base (`veiculos.json`) carrega a placa canônica `AAA9999`
 (maiúsculas, sem hífen). Cada fonte aplica uma *transformação de grafia* determinística ao
 escrever seus registros, para produzir as inconsistências propositais:

| Fonte | Grafia da placa | Exemplo (canônico `ABC1234`) |
|---|---|---|
| Abastecimento (CSV) | Mistura: ~50% com hífen `ABC-1234`, ~50% sem hífen `ABC1234` | `ABC-1234` |
| Multas (JSON/API) | Minúsculas, sem hífen | `abc1234` |
| Manutenção (XLSX) | Maiúsculas, sem hífen (canônico) | `ABC1234` |
| Licenciamento (SQLite) | Maiúsculas, mas com duplicatas (mesma placa, 2 linhas) | `ABC1234` (×2) |

**Racional**: A placa é a chave de reconciliação (constitution II, arquitetura §2). As grafias
 divergentes são o input esperado do pipeline (spec 003 fará a normalização para `AAA9999`).
 Os 2 veículos da demo mantêm placas válidas no formato canônico nas fontes que usam
 maiúsculas (manutenção, licenciamento), mas também aparecem com hífen/minúsculas nas outras
 — isso NÃO os invalida, porque a normalização do pipeline os recuperará (Edge Case da spec:
 "as inconsistências não podem tornar um veículo da demo inválido" refere-se a rejeição por
 `placa_invalida`, não a grafia divergente que normaliza corretamente).

**Geração de placas**: 3 letras + 4 dígitos, todas únicas no cadastro. Série determinística
 via `rng`.

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
