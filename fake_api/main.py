"""Mini-API FastAPI que serve as multas simuladas (Fonte 2 — spec 001, decisão D5).

Apenas serve o `multas.json` gerado por `data/gerador_dados.py` — não gera dados
(research R5). Contrato em `specs/001-fontes-dados-simuladas/contracts/api_multas.md`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException

logger = logging.getLogger("fake_api")

CAMINHO_MULTAS = Path(__file__).resolve().parent / "multas.json"

app = FastAPI(title="API fake de multas — Desafio 13 (frota municipal)")

_cache: list[dict] | None = None


def _carregar() -> list[dict]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CAMINHO_MULTAS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # detail genérico: o caminho/erro cru ficam só no log do servidor (sem vazar path)
            logger.exception("falha ao carregar multas.json")
            raise HTTPException(status_code=500, detail="fonte de multas indisponível") from exc
    return _cache


@app.get("/multas")
def listar_multas() -> list[dict]:
    return _carregar()


@app.get("/multas/{placa}")
def multas_por_placa(placa: str) -> list[dict]:
    # a fonte grafa placas em minúsculas (inconsistência propositais — R7)
    return [m for m in _carregar() if m["placa"] == placa.lower()]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
