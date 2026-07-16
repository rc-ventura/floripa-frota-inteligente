# Quickstart — Validação da Spec 002 (Modelo de Dados e Banco Consolidado)

**Branch**: `feature/002-modelo-dados-banco` | **Date**: 2026-07-16

Guia de validação executável dos critérios SC-001..SC-004 e FR-001..FR-007. Contratos em
`contracts/esquema_tabelas.md`; esquema completo em `data-model.md`.

## Pré-requisitos

- Python 3.12+ e `uv` (dependências: `uv sync` — inclui sqlalchemy, alembic, psycopg).
- Para o Cenário 5 (Postgres): Docker (`docker run postgres:16`) ou o compose da spec 007.
- Repositório na branch `feature/002-modelo-dados-banco`.

---

## Cenário 1 — Esquema completo do zero em 1 comando (FR-001..FR-007, SC-001)

```bash
rm -f db/frota.db            # ambiente limpo (SQLite default)
time python -m db.init_db    # < 1 min
```

**Esperado**: as 12 tabelas existem + `alembic_version`:

```bash
sqlite3 db/frota.db ".tables"
# alembic_version  licenciamento  multa            stg_licenciamento  veiculo
# alerta           limiar_config  stg_abastecimento stg_manutencao
# abastecimento    log_qualidade  stg_multas        manutencao
sqlite3 db/frota.db "SELECT COUNT(*) FROM limiar_config"   # → 9
```

## Cenário 2 — Idempotência (SC-004, edge case "recriação")

```bash
python -m db.init_db && python -m db.init_db   # 2ª execução: sem erro
sqlite3 db/frota.db "SELECT COUNT(*) FROM limiar_config"   # → continua 9 (sem duplicar)
```

Inserir um dado antes da re-execução e confirmar que sobrevive (nenhuma perda).

## Cenário 3 — Seed espelha a fonte única (FR-004)

```bash
python - <<'EOF'
import json, sqlite3
semente = json.load(open("data/seeds/limiares_semente.json"))
con = sqlite3.connect("db/frota.db")
banco = con.execute("SELECT tipo_veiculo, tipo_manutencao, limite_km, limite_dias, antecedencia_km, antecedencia_dias FROM limiar_config ORDER BY tipo_veiculo, tipo_manutencao").fetchall()
esperado = sorted([tuple(l.values()) for l in semente])
assert sorted(banco) == esperado, "seed diverge do JSON"
print("OK: limiar_config == limiares_semente.json (9 linhas)")
EOF
```

## Cenário 4 — Limiar editável em runtime (US2, SC-002 — momento da demo)

```bash
# com o sistema "rodando", altere um limiar direto no banco:
sqlite3 db/frota.db "UPDATE limiar_config SET limite_km = 4000 WHERE tipo_veiculo='leve' AND tipo_manutencao='troca_oleo'"
# nenhum restart: a próxima leitura (motor, spec 004) deve ver 4000.
# e o re-init NÃO desfaz a edição (upsert não sobrescreve):
python -m db.init_db
sqlite3 db/frota.db "SELECT limite_km FROM limiar_config WHERE tipo_veiculo='leve' AND tipo_manutencao='troca_oleo'"  # → 4000
```

*(Restaure depois: `UPDATE ... SET limite_km = 5000 ...` ou apague o banco e re-init.)*

> **Recalibração deliberada** (o inverso do cenário acima): editar `data/seeds/limiares_semente.json`
> NÃO altera bancos existentes em re-init (proteção da edição ao vivo). Para adotar novos valores
> do JSON num banco existente: `python -m db.seed_limiares --sobrescrever`.
>
> **Nota SC-002**: este cenário é o *proxy* verificável hoje ("nova leitura vê o novo valor");
> a verificação plena — "próxima verificação do **motor**" — acontece na spec 004, que herda do
> contrato a proibição de cache de processo.

## Cenário 5 — Mesmo esquema nos dois ambientes (D2, edge case "troca de banco")

```bash
docker run --rm -d --name pg-frota -e POSTGRES_PASSWORD=frota -e POSTGRES_DB=frota -p 5432:5432 postgres:16
DATABASE_URL="postgresql+psycopg://postgres:frota@localhost:5432/frota" python -m db.init_db
DATABASE_URL="postgresql+psycopg://postgres:frota@localhost:5432/frota" python -m db.init_db  # idempotente aqui também
docker stop pg-frota
```

**Esperado**: mesmas tabelas/constraints, zero alteração de código.

## Cenário 6 — Rastreabilidade e LGPD no esquema (US3, SC-003)

```bash
python - <<'EOF'
import sqlite3
con = sqlite3.connect("db/frota.db")
tabelas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
consolidadas = ["veiculo","abastecimento","manutencao","multa","licenciamento"]
for t in consolidadas:
    cols = [c[1] for c in con.execute(f"PRAGMA table_info({t})")]
    assert "fonte_origem" in cols, f"{t} sem fonte_origem"
for t in [t for t in tabelas if t.startswith("stg_")]:
    cols = [c[1] for c in con.execute(f"PRAGMA table_info({t})")]
    assert "carga_em" in cols and "fonte_origem" in cols, f"{t} sem carimbo de carga"
# LGPD: nenhuma coluna de identidade real e nenhuma tabela de-para
proibidas = {"nome","cpf","matricula","cnh"}
for t in consolidadas + ["alerta","limiar_config"]:
    cols = {c[1] for c in con.execute(f"PRAGMA table_info({t})")}
    assert not (cols & proibidas), f"{t} tem coluna proibida: {cols & proibidas}"
assert not [t for t in tabelas if "condutor" in t], "existe tabela de condutor (de-para?)"
print("OK: fonte_origem em 100% das consolidadas; staging com carimbo; zero de-para/identidade real")
EOF
```

*(Nota: `stg_multas.cnh` existe por design — staging é bruto; o teste acima cobre as consolidadas.)*

## Cenário 7 — Suíte automatizada

```bash
uv run pytest tests/test_db.py -v
```

Cobre: criação do zero, idempotência dupla, seed == JSON, edição runtime sobrevive a re-init,
placa inválida rejeitada (`@validates` + CHECK), índice único parcial de alerta ativo
(duplicata rejeitada; resolvido não bloqueia novo ativo), introspecção LGPD.

---

## Próximos passos (fora desta spec)

- **Spec 003**: extratores gravam em `stg_*`, transform normaliza (regex/vocabulários deste
  contrato) e load faz upsert pelas chaves UNIQUE declaradas.
- **Spec 004**: motor lê `limiar_config` a cada ciclo e insere em `alerta` respeitando
  `ux_alerta_ativo`.
- **Spec 007**: `docker compose` sobe Postgres + `python -m db.init_db` no boot.
