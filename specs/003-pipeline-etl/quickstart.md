# Quickstart — Validação da Spec 003 (Pipeline ETL)

**Branch**: `feature/003-pipeline-etl` | **Date**: 2026-07-17

Guia de validação executável dos critérios SC-001..SC-005 e das user stories US1–US4.
Contrato de invocação em `contracts/ciclo_pipeline.md`; mapeamento por fonte em
`data-model.md`.

## Pré-requisitos

- `uv sync` (o venv ativo dispensa o prefixo `uv run`).
- Esquema criado: `uv run python -m db.init_db` (contrato 002).
- Fonte 1 na pasta monitorada: `cp data/seeds/abastecimento.csv data/inbox/`.
- Fonte 2 no ar (terminal separado): `uv run uvicorn fake_api.main:app --port 8000`.
- Fontes 3 e 4 são os arquivos de `data/seeds/` (defaults das env vars — nada a fazer).
- Ambiente limpo entre cenários destrutivos: `rm -f db/frota.db && uv run python -m db.init_db`.

---

## Cenário 1 — Ciclo completo popula staging bruto com rastreabilidade (US1, SC-003)

```bash
uv run python -m pipeline.run_etl
```

**Esperado**: os 4 stagings populados com dado **bruto** (placa com hífen/minúscula intacta,
vírgula decimal preservada) e carimbo:

```bash
sqlite3 db/frota.db "SELECT COUNT(*), MIN(carga_em) FROM stg_abastecimento"
sqlite3 db/frota.db "SELECT DISTINCT fonte_origem FROM stg_multas"      # http://localhost:8000/multas@sha256:...
sqlite3 db/frota.db "SELECT DISTINCT aba_origem FROM stg_manutencao"    # 3 abas do XLSX
sqlite3 db/frota.db "SELECT COUNT(*) FROM stg_licenciamento"            # inclui duplicatas (dedup é do transform)
```

## Cenário 2 — Qualidade: normaliza o que dá, rejeita com motivo (US2, SC-002)

Após o Cenário 1:

```bash
# placas todas canônicas no consolidado (nenhum hífen/minúscula):
sqlite3 db/frota.db "SELECT COUNT(*) FROM abastecimento WHERE placa GLOB '*[a-z-]*'"   # → 0
# vocabulário padronizado:
sqlite3 db/frota.db "SELECT DISTINCT tipo FROM manutencao"       # ⊆ {troca_oleo,filtros,pneus,revisao_geral}
sqlite3 db/frota.db "SELECT DISTINCT categoria FROM manutencao"  # ⊆ {preventiva,corretiva}
# rejeições com motivo (nunca silencioso):
sqlite3 db/frota.db "SELECT motivo_rejeicao, COUNT(*) FROM log_qualidade GROUP BY 1"
```

**Esperado**: cada inconsistência **inválida** de `data/seeds/INCONSISTENCIAS.md` presente
em `log_qualidade` com o motivo previsto (ex.: duplicatas do licenciamento → `duplicado`);
as normalizáveis (hífen, vírgula, minúscula, serial Excel) **não** aparecem no log — viram
dado consolidado.

## Cenário 3 — LGPD: `cnh` morre na fronteira staging→consolidado (FR-011)

```bash
sqlite3 db/frota.db "SELECT COUNT(*) FROM stg_multas WHERE cnh IS NOT NULL"   # > 0 (bruto auditável)
uv run python - <<'EOF'
import sqlite3
con = sqlite3.connect("db/frota.db")
cnhs = {r[0] for r in con.execute("SELECT cnh FROM stg_multas WHERE cnh IS NOT NULL")}
for t in ["veiculo","abastecimento","manutencao","multa","licenciamento","alerta"]:
    for row in con.execute(f"SELECT * FROM {t}"):
        assert not (set(map(str, row)) & cnhs), f"CNH vazou em {t}!"
print("OK: nenhuma CNH em nenhuma consolidada")
EOF
```

## Cenário 4 — Idempotência de ponta a ponta (US3, SC-001)

```bash
uv run python -m pipeline.run_etl        # 2ª execução, nada mudou nas fontes
```

**Esperado**: resumo com `situacao=sem_novidade` nas 5 fontes; contagens idênticas em
consolidadas, staging **e** `log_qualidade`:

```bash
for t in veiculo abastecimento manutencao multa licenciamento log_qualidade stg_abastecimento; do
  echo "$t: $(sqlite3 db/frota.db "SELECT COUNT(*) FROM $t")"
done
# rode antes e depois da 2ª execução — números iguais
```

## Cenário 5 — Arquivo novo na pasta = momento da demo (US3.2, FR-010)

```bash
sqlite3 db/frota.db "SELECT km_atual FROM veiculo WHERE placa = (SELECT placa FROM veiculo ORDER BY placa LIMIT 1)"  # anote o km do veículo A da demo
cp data/seeds/gatilho_demo_abastecimento.csv data/inbox/
uv run python -m pipeline.run_etl
```

**Esperado**: só o CSV novo é processado (`abastecimento: extraidos = 1`; demais
`sem_novidade`); `veiculo.km_atual` do veículo A sobe para ≥ 4501 (contrato da spec 001 —
é o que cruzará a antecedência no motor da spec 004). Repetir o `cp` com outro nome de
arquivo (mesmo conteúdo) + novo ciclo → nada muda (hash — edge case "renomeado").

## Cenário 6 — Resiliência: fonte fora não derruba o ciclo (US4, SC-005)

```bash
# derrube a fake_api (Ctrl-C no terminal dela) e rode o ciclo:
uv run python -m pipeline.run_etl
```

**Esperado**: exit code `0`; resumo com `multas: indisponivel` e as demais fontes seguindo
normalmente (`ok` ou `sem_novidade` — novidade não é pré-condição do isolamento);
diagnóstico registrado:

```bash
sqlite3 db/frota.db "SELECT fonte, motivo_rejeicao FROM log_qualidade WHERE motivo_rejeicao='fonte_indisponivel' ORDER BY carga_em DESC LIMIT 1"
# → multas | fonte_indisponivel
```

*(Religue a API depois: o ciclo seguinte volta a `ok`/`sem_novidade` sozinho.)*

## Cenário 7 — Tempo de ciclo (SC-004)

```bash
time uv run python -m pipeline.run_etl    # < 1 min (volume da PoC) — na prática, segundos
```

## Cenário 8 — Suíte automatizada

```bash
uv run pytest tests/test_pipeline.py -v
```

Cobre: US1 (staging bruto + carimbo), US2/SC-002 (cada inconsistência da spec 001 →
normalização ou motivo), US3/SC-001 (dupla execução, estado idêntico incluindo log),
US4/SC-005 (fonte fora, demais seguem), FR-010 (km_atual monotônico), FR-011 (CNH nunca
consolidada), edge cases (arquivo renomeado, linha corrompida no meio do lote,
`veiculo_desconhecido`).

---

## Próximos passos (fora desta spec)

- **Spec 004**: APScheduler agenda `executar_ciclo()` + motor no intervalo da demo
  (env var do agendador); motor lê o consolidado que este pipeline mantém.
- **Spec 007**: compose sobe `db` + `fake_api` + app; env vars do contrato
  (`MULTAS_API_URL=http://fake_api:8000` etc.).
