import httpx
from sqlalchemy import insert
from sqlalchemy.engine import Engine
 
from db.models import StgMultas
from pipeline.config import multas_api_url
from pipeline.extract import fonte_ja_vista, montar_fonte_origem, novo_lote, sha256_conteudo, to_text
 
# Todos os campos do payload — staging retém o bruto completo (trilha de auditoria).
_CAMPOS = ["placa", "data", "gravidade", "valor", "condutor", "cnh", "situacao", "codigo_infracao"]
 
 
def extrair_multas(engine: Engine) -> dict:
    """GET /multas; hash do corpo; se hash já visto → sem_novidade (R1); senão
    grava payload bruto completo em stg_multas."""
    url = f"{multas_api_url()}/multas"
    resp = httpx.get(url, timeout=5.0)
    resp.raise_for_status()

    hash12 = sha256_conteudo(resp.content)
    if fonte_ja_vista(engine, "stg_multas", hash12):
        return {"situacao": "sem_novidade", "extraidos": 0, "consolidados": 0, "rejeitados": 0}
    
    multas = resp.json()
    carga_em = novo_lote()
    fonte_origem = montar_fonte_origem(url, hash12)
    linhas = [{
        "carga_em": carga_em,
        "fonte_origem": fonte_origem,
        **{c: to_text(m.get(c)) for c in _CAMPOS},
    } for m in multas]
    
    with engine.begin() as conn:
        conn.execute(insert(StgMultas.__table__), linhas)
    
    return {"situacao": "ok", "extraidos": len(linhas), "consolidados": 0, "rejeitados": 0}
 