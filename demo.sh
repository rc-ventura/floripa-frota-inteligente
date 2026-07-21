#!/usr/bin/env bash
# demo.sh — Roteiro reproduzível da demo ao vivo (spec 004: motor de alertas).
# Sobe fake_api + scheduler (ETL -> Motor), deposita o CSV de gatilho e mostra o
# alerta km disparado — o caminho crítico da métrica binária do briefing.
#
# Uso:   ./demo.sh
# Parar: Ctrl-C (derruba fake_api e scheduler, limpa o inbox)

set -euo pipefail
cd "$(dirname "$0")"

INTERVALO="${CICLO_INTERVALO_SEGUNDOS:-15}"

echo "[demo] Limpando banco para cena reproduzivel..."
rm -f db/frota.db
rm -f data/inbox/*.csv 2>/dev/null || true
uv run python -m db.init_db

echo "[demo] Subindo fake_api de multas (background, porta 8000)..."
uv run uvicorn fake_api.main:app --port 8000 >/tmp/demo_fake_api.log 2>&1 &
FAKE_API_PID=$!

cleanup() {
  echo
  echo "[demo] Encerrando..."
  kill "$FAKE_API_PID" 2>/dev/null || true
  rm -f data/inbox/*.csv 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[demo] Aguardando fake_api subir..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:8000/multas >/dev/null 2>&1; then
    echo "[demo] fake_api pronta."
    break
  fi
  sleep 0.3
done

echo "[demo] Subindo scheduler (ciclo=${INTERVALO}s — ETL -> Motor, ordem arquitetura §8)..."
echo "[demo] 1o ciclo roda imediatamente. Em outro terminal, quando quiser o gatilho:"
echo "[demo]   cp data/seeds/gatilho_demo_abastecimento.csv data/inbox/"
echo "[demo] Ctrl-C aqui encerra tudo."
echo

CICLO_INTERVALO_SEGUNDOS="$INTERVALO" uv run python -m scheduler
