# Feature Specification: Modelo de Dados e Banco Consolidado

**Feature Branch**: `feature/002-modelo-dados-banco`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "Materializar o ERD da arquitetura v1 (seção 4): tabelas de staging, consolidadas, LIMIAR_CONFIG, ALERTA e log_qualidade, com limiares iniciais parametrizados e rastreabilidade em todas as tabelas."

**Papel responsável**: ⚙️ Backend · **Fases do kanban**: Fase 0 (tasks 3–4), Fase 1 (task 3) · **Depende de**: nenhuma (pode andar em paralelo com 001) · 🔴 demo-crítico (task 4 da Fase 0)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Esquema completo criado do zero (Priority: P1)

Como membro da equipe, preciso subir o banco completo (staging, consolidadas, configuração, alertas e log de qualidade) a partir de um repositório limpo, para que pipeline, motor e dashboard tenham o contrato de dados sobre o qual trabalhar.

**Why this priority**: O banco é o único canal de comunicação entre as camadas (princípio central da arquitetura); sem o esquema, nenhuma integração entre frentes é possível.

**Independent Test**: Em ambiente limpo, criar o banco via mecanismo automatizado do repositório e verificar que todas as tabelas do ERD existem com os campos e relacionamentos previstos.

**Acceptance Scenarios**:

1. **Given** um ambiente sem banco, **When** o esquema é criado pelo mecanismo automatizado, **Then** existem as tabelas consolidadas (VEICULO, ABASTECIMENTO, MANUTENCAO, MULTA, LICENCIAMENTO, LIMIAR_CONFIG, ALERTA), uma staging por fonte (`stg_*`) e `log_qualidade`.
2. **Given** o esquema criado, **When** um registro consolidado é inserido, **Then** a placa segue o formato canônico (maiúsculas, sem hífen; antigo `AAA9999` ou Mercosul `AAA9A99` — regex `^[A-Z]{3}\d[A-Z\d]\d{2}$`, ADR-001) e os relacionamentos do ERD (veículo ↔ eventos) são respeitados.

---

### User Story 2 - Limiares como dados, não código (Priority: P1)

Como apresentador da demo, preciso alterar um limiar de manutenção com o sistema rodando e ver o motor de alertas reagir, para demonstrar a parametrização por tipo de veículo/manutenção exigida pelo briefing (4.3).

**Why this priority**: É exigência explícita do briefing e um momento planejado da demo; além disso o cenário determinístico (spec 001) depende dos valores definidos aqui.

**Independent Test**: Alterar um valor em LIMIAR_CONFIG sem reiniciar nada e verificar que a próxima verificação do motor usa o novo valor.

**Acceptance Scenarios**:

1. **Given** o banco recém-criado, **When** consultada LIMIAR_CONFIG, **Then** existem as 9 linhas da tabela-semente da spec 001 (≥2 tipos de veículo × ≥2 tipos de manutenção), com limite de km, limite de dias e antecedências preenchidos.
2. **Given** o sistema em execução, **When** um limiar é alterado diretamente na configuração, **Then** nenhuma alteração de código ou reinicialização é necessária para o novo valor valer.

---

### User Story 3 - Rastreabilidade e LGPD embutidas no modelo (Priority: P2)

Como responsável por conformidade, preciso que toda tabela consolidada carregue a origem do dado (`fonte_origem`) e que condutores existam apenas pseudonimizados, para que auditabilidade (Lei 14.133) e minimização (LGPD) sejam propriedades do modelo, não remendos.

**Why this priority**: Compliance é critério de avaliação (e possível desclassificação), mas depende do esquema base existir.

**Independent Test**: Inspecionar o esquema: toda tabela consolidada tem `fonte_origem`; staging tem carimbo de carga; não existe nenhuma estrutura que vincule pseudônimo a identidade real.

**Acceptance Scenarios**:

1. **Given** qualquer tabela consolidada, **When** inspecionada, **Then** possui campo `fonte_origem` capaz de apontar a carga e a fonte que trouxeram o dado.
2. **Given** o esquema completo, **When** procurada uma tabela de-para condutor→identidade real, **Then** ela não existe na PoC.

### Edge Cases

- Recriação: rodar a criação do esquema sobre um banco já existente não pode destruir dados nem falhar (migrations idempotentes/versionadas).
- Par (tipo_veiculo, tipo_manutencao) sem limiar cadastrado: o modelo deve permitir ao motor detectar a ausência (não inventar default silencioso).
- Troca de banco local ↔ banco da demo: o mesmo esquema deve funcionar nos dois ambientes previstos na arquitetura (D2) sem alteração de código.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O esquema MUST materializar as 7 entidades do diagrama do ERD da arquitetura v2 (seção 4 — inclui `km_hodometro` nullable no ABASTECIMENTO, ADR-002, e `categoria` na MANUTENCAO, ADR-003) mais as tabelas de apoio listadas fora do diagrama (`stg_*` por fonte e `log_qualidade`), com placa canônica (formatos `AAA9999` e `AAA9A99` — ADR-001) como chave natural de VEICULO e chave estrangeira dos eventos.
- **FR-002**: MUST existir uma tabela de staging por fonte (`stg_*`), espelhando o formato bruto, com carimbo de data/hora da carga e identificação do arquivo/endpoint de origem.
- **FR-003**: MUST existir `log_qualidade` (fonte, registro bruto, motivo da rejeição, momento da carga) para receber registros rejeitados pelo pipeline.
- **FR-004**: LIMIAR_CONFIG MUST ser tabela de dados editável em tempo de execução, semeada com ≥2 tipos de veículo × ≥2 tipos de manutenção (limite_km, limite_dias, antecedencia_km, antecedencia_dias) — exatamente a tabela-semente de 9 linhas da spec 001 (`data/seeds/limiares_semente.json`, fonte única; 3 tipos de veículo × até 4 manutenções).
- **FR-005**: ALERTA MUST suportar histórico permanente (situação `ativo`/`resolvido`, nunca apagado) e vínculo ao limiar que o parametrizou.
- **FR-006**: Toda tabela consolidada MUST carregar `fonte_origem`; condutores MUST existir apenas como `condutor_pseudo` (sem tabela de-para na PoC).
- **FR-007**: A criação do esquema MUST ser automatizada e reproduzível (versionada via migrations), executável em um comando a partir do repositório limpo.

### Key Entities

- **VEICULO**: placa canônica (PK), tipo, modelo, ano, secretaria, km atual.
- **ABASTECIMENTO / MANUTENCAO / MULTA**: eventos por placa, com valor, data, campos específicos e `fonte_origem`. ABASTECIMENTO inclui `km_hodometro` (int, nullable — leitura do odômetro no abastecimento; série temporal de km usada pelo painel de custos, ADR-002). MANUTENCAO inclui `categoria` (`preventiva` | `corretiva` — habilita o comparativo corretiva×preventiva do painel de custos, ADR-003 item 7).
- **LICENCIAMENTO**: situação e vencimento por placa (1:1).
- **LIMIAR_CONFIG**: parametrização de limites por tipo de veículo × tipo de manutenção.
- **ALERTA**: notificação gerada, com gatilho (km/tempo), momento e situação.
- **stg_* / log_qualidade**: staging bruto por fonte e trilha de rejeições.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Banco completo criado do zero em um comando, em menos de 1 minuto, nos dois ambientes previstos (local e demo).
- **SC-002**: Alterar um limiar reflete na próxima verificação do motor sem reinicialização — demonstrável ao vivo.
- **SC-003**: 100% das tabelas consolidadas possuem `fonte_origem` preenchível; zero estruturas ligando pseudônimo a identidade real.
- **SC-004**: Executar a criação do esquema duas vezes seguidas não gera erro nem perda de dados.

## Assumptions

- A camada de acesso permite começar em banco local leve e trocar para o banco da demo sem reescrever código (decisão D2 da arquitetura); o esquema é o mesmo nos dois.
- Valores iniciais de limiar são os da tabela-semente de 9 linhas definida na spec 001 (Clarifications 2026-07-14, atualizada 2026-07-15): `troca_oleo`/`leve` = 5.000 km / 180 dias (uso severo urbano — justificativa no ADR-003), `revisao_geral` leve/ambulância = 10.000 km / 365 dias (plano padrão de fabricante — ADR-003 item 9), `troca_oleo`/`caminhao` = 10.000 km, etc. A migration de seed usa exatamente esses valores literais (`data/seeds/limiares_semente.json` é o espelho).
- Evolução documentada (fora do escopo da PoC): planos de manutenção por **modelo/marca de fabricante** entram como coluna adicional em LIMIAR_CONFIG (`modelo`, nullable) com regra de resolução "mais específico vence, senão cai no tipo de veículo" — mudança de dados, não de código (constitution V; ADR-003 item 9). O briefing (4.3) pede parametrização por tipo, que é o que a PoC entrega.
- Constraints rígidas demais no staging são indesejadas: staging aceita dado bruto sujo; a qualidade é imposta na transformação (spec 003), não na entrada do staging.

## Referências

- Arquitetura: `wiki/arquitetura_tecnica_desafio13_v2.md` (seções 4, 7-D2/D7/D8 e 10)
- ADRs: `docs/decisoes/ADR-001-placa-canonica-dois-formatos.md` · `docs/decisoes/ADR-002-persistir-km-hodometro-abastecimento.md` · `docs/decisoes/ADR-003-calibracao-realismo-fontes-simuladas.md`
- Kanban: `wiki/kanban_tasks_desafio13_frota_municipal.md` (Fase 0 t3–t4, Fase 1 t3)
