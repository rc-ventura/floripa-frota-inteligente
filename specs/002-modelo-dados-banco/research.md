# Research — Modelo de Dados e Banco Consolidado (Spec 002)

**Branch**: `feature/002-modelo-dados-banco` | **Date**: 2026-07-16

Resolução dos unknowns técnicos. As decisões de *o quê* (entidades, campos) vêm do ERD da
arquitetura v2 §4 e dos ADRs 001–003; este documento cobre o *como* implementar.

---

## R1. Camada de acesso: SQLAlchemy 2.x declarativo + `DATABASE_URL`

**Decisão**: Modelos declarativos SQLAlchemy 2.x (`DeclarativeBase`, `Mapped[...]`/`mapped_column`)
em `db/models.py`. A engine é criada a partir de `DATABASE_URL` (variável de ambiente), com
default `sqlite:///db/frota.db` quando ausente — resolvida em um único ponto (`db/config.py`).

**Racional**: é exatamente a decisão D2 da arquitetura ("SQLAlchemy permite começar em SQLite
localmente e trocar sem reescrever código"). A API 2.x tipada reduz erro e é o estilo atual da
biblioteca. Um único ponto de resolução de URL evita que camadas (pipeline/motor/dashboard)
inventem conexões próprias — todas importam `db.config.get_engine()`.

**Alternativas consideradas**:
- SQL puro/DDL manual: rejeitado — dupla manutenção (modelos × DDL) e sem portabilidade
  SQLite↔Postgres garantida.
- SQLModel/outro ORM: rejeitado — D2 já fixa SQLAlchemy; adicionar camada extra viola VII.

---

## R2. Migrations: Alembic com migration inicial única

**Decisão**: Alembic (`db/migrations/`), com `env.py` importando `db.models.Base.metadata`
(autogenerate disponível para evoluções) e **uma** migration inicial `0001_esquema_inicial`
criando as 12 tabelas + índices. `alembic upgrade head` é o mecanismo de criação — naturalmente
idempotente (re-executar em banco já migrado é no-op; SC-004).

**Racional**: FR-007 pede explicitamente criação "versionada via migrations". Alembic é o
companheiro padrão do SQLAlchemy, funciona igual em SQLite e Postgres, e o versionamento
(`alembic_version`) dá o "recriação não destrói dados" do edge case da spec de graça.

**Alternativas consideradas**:
- `Base.metadata.create_all()`: rejeitado como mecanismo oficial — não é versionado (FR-007) e
  não registra evolução de esquema; permanece útil em fixtures de teste.
- Migrations SQL artesanais: rejeitado — sem autogenerate, mais chance de divergência dos modelos.

**Nota SQLite**: `render_as_batch=True` no `env.py` (batch mode) para futuras alterações de
coluna funcionarem em SQLite, que não suporta `ALTER` completo.

---

## R3. Validação da placa canônica dual (ADR-001)

**Decisão**: A regex canônica `^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$` vive em `db/models.py` como
constante exportada (`REGEX_PLACA_CANONICA`) e é aplicada em **nível de aplicação** via
`@validates("placa")` do SQLAlchemy (levanta `ValueError` antes do INSERT). No banco, um
`CheckConstraint("length(placa) = 7")` portátil serve de segunda linha de defesa.

**Racional**: CHECK com regex não é portátil (Postgres usa `~`, SQLite usa `GLOB/REGEXP` com
extensão) — a validação em Python roda idêntica nos dois ambientes (D2). Exportar a constante
dá à spec 003 a fonte única do contrato de normalização (o pipeline normaliza; o modelo valida).

**Alternativas consideradas**:
- CHECK regex específico por dialeto: rejeitado — bifurca o esquema entre ambientes.
- Validar só no pipeline: rejeitado — o modelo é o contrato; defesa em profundidade barata.

---

## R4. Seed da LIMIAR_CONFIG lê o JSON da spec 001 (fonte única)

**Decisão**: `db/seed_limiares.py` lê `data/seeds/limiares_semente.json` (artefato versionado
da spec 001) e faz **upsert** por chave natural `(tipo_veiculo, tipo_manutencao)` — inserir se
não existe, não sobrescrever se já existe (preserva ajustes feitos ao vivo na demo; re-seed
idempotente, SC-004). O caminho do JSON é resolvido relativo à raiz do repo.

**Racional**: o Complexity Tracking da spec 001 registrou a duplicação "por convenção" (mesmos
literais no JSON e na migration) como dívida. Ler o JSON elimina a segunda cópia — os valores
passam a ter **uma** fonte de verdade, e recalibrar limiar de geração e de motor é editar um
arquivo. Não é violação de camadas (constitution VI): o JSON é configuração versionada do
repositório, não um "arquivo-fonte de dados" da pasta monitorada.

**Recalibração (achado U1 do speckit-analyze)**: a contrapartida do "não sobrescrever" é que
editar o JSON **não** atualiza bancos existentes em re-init. O caminho deliberado de
recalibração é `python -m db.seed_limiares --sobrescrever` (adota os valores do JSON,
descartando edições locais) — documentado no quickstart C4 e no contrato.

**Alternativas consideradas**:
- Valores literais na migration (plano original da 001): rejeitado — duas fontes de verdade.
- Seed que sobrescreve sempre: rejeitado — apagaria a alteração de limiar feita ao vivo na
  demo a cada re-init (US2/SC-002 seria frágil).

---

## R5. Staging frouxo: tudo TEXT + carimbo de carga

**Decisão**: 4 tabelas `stg_*` espelhando coluna a coluna o formato bruto de cada fonte
(contratos da spec 001), com **todas as colunas de dados como TEXT nullable**, mais o trio de
rastreabilidade: `id` (PK), `carga_em` (DATETIME NOT NULL) e `fonte_origem` (TEXT NOT NULL —
nome do arquivo/endpoint). `stg_manutencao` inclui `aba_origem` (a aba do XLSX). Sem FKs, sem
CHECKs, sem uniques.

**Racional**: assumption explícita da spec ("constraints rígidas demais no staging são
indesejadas; a qualidade é imposta na transformação"). Datas como TEXT preservam o formato
original (`14/07/2026`, serial Excel `46068`) — evidência de rastreabilidade para a banca.

**Nota LGPD**: `stg_multas` carrega `cnh` (sintética) porque staging é bruto por definição
(constitution II); o descarte acontece na consolidação (spec 003 FR-011) e a política de
expurgo se apoia em `carga_em` (arquitetura §10).

---

## R6. Idempotência do ALERTA no banco: índice único parcial

**Decisão**: `ALERTA` ganha índice único parcial `ux_alerta_ativo` sobre
`(placa, tipo_gatilho, coalesce(limiar_id, -1))` com filtro `situacao = 'ativo'` — o banco
garante no máximo 1 alerta ativo por (placa, gatilho, limiar), mesmo se o motor (spec 004)
tiver bug ou correr em duplicidade. `limiar_id` é **nullable** (alertas `dados_insuficientes`
não têm limiar — spec 004 US4) e o `coalesce` evita o comportamento "NULLs nunca conflitam"
dos índices únicos. Campo `detalhe` (TEXT NULL) registra "o que falta" no `dados_insuficientes`
(spec 004 FR-005). Índices parciais e por expressão funcionam em SQLite ≥3.9 e Postgres.

**Racional**: a idempotência do motor é FR-003 da spec 004, mas a garantia estrutural pertence
ao esquema — defesa em profundidade que torna o SC-002 da 004 ("10 execuções, zero duplicados")
trivialmente verdadeiro. Histórico permanente: nenhuma exclusão; transição `ativo → resolvido`
(FR-005 desta spec).

**Alternativas consideradas**:
- Unique total (sem filtro): rejeitado — impediria reabrir alerta após um resolvido (spec 004
  US3 cenário 3: resolvido não bloqueia recorrência).
- Garantir só no código do motor: rejeitado — constraint é barata e à prova de concorrência.

---

## R7. Chaves de upsert das consolidadas (contrato para a spec 003)

**Decisão**: cada consolidada de evento declara a UNIQUE que o pipeline usará no upsert:

| Tabela | Chave de upsert (UNIQUE) | Racional |
|---|---|---|
| `manutencao` | `(placa, data, tipo)` | chave natural oficial da dedup (spec 003 FR-004) |
| `abastecimento` | `(placa, data, km_hodometro)` | hodômetro é monotônico/único por abastecimento (R12 da 001); NULLs de km não conflitam — dedup fina fica no pipeline |
| `multa` | `(placa, data, valor, coalesce(condutor_pseudo, ''))` — índice único de expressão `ux_multa_upsert` | melhor chave natural disponível sem persistir codigo_infracao (fonte-apenas, ADR-003); o coalesce faz multas sem condutor também colidirem (ADR-004 — sem ele, NULL≠NULL deixava duplicatas passarem) |
| `licenciamento` | `placa` (PK, 1:1) | upsert = atualizar vencimento/situação mais recentes |
| `veiculo` | `placa` (PK) | upsert de cadastro |

**Racional**: upsert idempotente (spec 003 FR-006) exige chave no **banco**; deixar para o
pipeline inventar seria contrato implícito. As escolhas pragmáticas (multa/abastecimento) estão
documentadas no contrato com suas limitações.

---

## R8. `fonte_origem` em VEICULO (adição consciente ao ERD)

**Decisão**: `veiculo` ganha `fonte_origem` (TEXT NOT NULL), embora o diagrama do ERD v2 não o
liste para essa entidade.

**Racional**: a constitution II exige `fonte_origem` em **toda** tabela consolidada, e VEICULO é
consolidada (o cadastro emerge das fontes na reconciliação por placa — spec 003). O diagrama
mostra os campos de domínio; a exigência transversal de auditabilidade prevalece (ordem de
desempate: constitution > diagrama). Registrado aqui e no data-model para a revisão do time;
não altera decisão de arquitetura (é aplicação do princípio já ratificado).

---

## R9. Dependências adicionadas ao `pyproject.toml`

**Decisão**: `sqlalchemy>=2.0`, `alembic>=1.13`, `psycopg[binary]>=3.1` no grupo principal
(pipeline/motor/dashboard também consumirão). Nada no dev-group além do já existente.

**Racional**: mínimas para D2 nos dois ambientes; `psycopg` v3 é o driver atual para
PostgreSQL 16, e o extra `[binary]` dispensa toolchain de compilação na máquina da demo.
