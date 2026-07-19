import pandas as pd
from sqlalchemy import insert
from sqlalchemy.engine import Engine
 
from db.models import StgAbastecimento
from pipeline.config import inbox_dir
from pipeline.extract import fonte_ja_vista, montar_fonte_origem, novo_lote, sha256_conteudo, to_text
 

 # Colunas do contrato 001 — lidas por nome (não por posição).
_COLUNAS = ["placa", "data", "litros", "valor", "condutor", "km"]
 
def extrair_abastecimento(engine: Engine) -> dict:
    """Varre a pasta monitorada; cada CSV novo (por hash) vira um lote em
    stg_abastecimento com colunas verbatim. Um carga_em por fonte/ciclo (R2)."""
    
    carga_em = novo_lote()
    csvs = sorted(inbox_dir().glob("*.csv"))
    linhas: list[dict] = []
    arquivos_novos = 0

    for caminho in csvs:
        hash12 = sha256_conteudo(caminho.read_bytes())
        if fonte_ja_vista(engine, "stg_abastecimento", hash12):
            continue
        arquivos_novos += 1
        fonte_origem = montar_fonte_origem(str(caminho), hash12)
        # dtype=str: ler tudo como texto 
        df = pd.read_csv(caminho, dtype=str)
        for _, row in df.iterrows():
            linhas.append({
                "carga_em": carga_em,
                "fonte_origem": fonte_origem,
                **{c: (None if pd.isna(row[c]) else to_text(row[c])) for c in _COLUNAS}
            })

    if linhas:
        with engine.begin() as conn:
            conn.execute(insert(StgAbastecimento.__table__), linhas)

    situacao = "ok" if arquivos_novos > 0 else "sem_novidade"
    return {"situacao": situacao, "extraidos": len(linhas), "consolidados": 0, "rejeitados": 0}
