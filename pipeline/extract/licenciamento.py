import sqlite3
from sqlalchemy import insert
from sqlalchemy.engine import Engine
 
from db.models import StgLicenciamento
from pipeline.config import sqlite_licenciamento
from pipeline.extract import fonte_ja_vista, montar_fonte_origem, novo_lote, sha256_conteudo, to_text

def extrair_licenciamento(engine: Engine) -> dict:
    """Conexão somente-leitura ao SQLite legado; hash do arquivo; se já visto →
    sem_novidade (R1). Linhas brutas (incluindo duplicatas) → stg_licenciamento."""
    
    caminho = sqlite_licenciamento()
    hash12 = sha256_conteudo(caminho.read_bytes())
    if fonte_ja_vista(engine, "stg_licenciamento", hash12):
        return {"situacao": "sem_novidade", "extraidos": 0, "consolidados": 0, "rejeitados": 0}
 
    carga_em = novo_lote()
    fonte_origem = montar_fonte_origem(str(caminho), hash12)

    # URI mode=ro: previne escrita acidental no legado
    con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT placa, vencimento, situacao FROM licenciamento").fetchall()
    finally:
        con.close()
    
    linhas = [{
        "carga_em": carga_em,
        "fonte_origem": fonte_origem,
        "placa": to_text(r[0]),
        "vencimento": to_text(r[1]),
        "situacao": to_text(r[2]),
    } for r in rows]

    if linhas:
        with engine.begin() as conn:
            conn.execute(insert(StgLicenciamento.__table__), linhas)

    return {"situacao": "ok", "extraidos": len(linhas), "consolidados": 0, "rejeitados": 0,
            "carga_em": carga_em}
