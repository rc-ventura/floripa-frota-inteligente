import logging
 
import pandas as pd
from sqlalchemy import insert
from sqlalchemy.engine import Engine
 
from db.models import StgManutencao
from pipeline.config import xlsx_manutencao
from pipeline.extract import fonte_ja_vista, montar_fonte_origem, novo_lote, sha256_conteudo, to_text
 
logger = logging.getLogger("pipeline.manutencao")

# Colunas esperadas em cada aba (contrato 001 formatos_arquivo.md).
_COLUNAS = ["placa", "data", "tipo", "categoria", "km_no_momento", "valor"]
 
def extrair_manutencao(engine: Engine) -> dict:
    """Lê todas as abas do XLSX; hash do arquivo; se já visto → sem_novidade (R1).
    Aba sem colunas esperadas → warning e skip (edge case 'aba inesperada')."""

    caminho = xlsx_manutencao()
    hash12 = sha256_conteudo(caminho.read_bytes())
    if fonte_ja_vista(engine, "stg_manutencao", hash12):
        return {"situacao": "sem_novidade", "extraidos": 0, "consolidados": 0, "rejeitados": 0}
 
    carga_em = novo_lote()
    fonte_origem = montar_fonte_origem(str(caminho), hash12)
    # sheet_name=None → dict {nome_aba: DataFrame} com todas as abas
    abas = pd.read_excel(caminho, sheet_name=None, dtype=str) 
    linhas: list[dict] = []

    for nome_aba, df in abas.items():
        if not set(_COLUNAS) <= set(df.columns):
            logger.warning("aba %r sem colunas esperadas — ignorada", nome_aba)
            continue
        for _, row in df.iterrows():
             linhas.append({
                "carga_em": carga_em,
                "fonte_origem": fonte_origem,
                **{c: (None if pd.isna(row[c]) else to_text(row[c])) for c in _COLUNAS},
                "aba_origem": nome_aba,
            })
 
    if linhas:
        with engine.begin() as conn:
            conn.execute(insert(StgManutencao.__table__), linhas)
 
    return {"situacao": "ok", "extraidos": len(linhas), "consolidados": 0, "rejeitados": 0}
