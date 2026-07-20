import json

from sqlalchemy import func
from sqlalchemy.engine import Engine

from db.models import Veiculo
from pipeline.config import cadastro_veiculos
from pipeline.extract import fonte_ja_vista, montar_fonte_origem, sha256_conteudo
from pipeline.load.upsert import dialeto_insert

# Descritivos anuláveis: coalesce-preserva-não-nulo (ADR-005) — um cadastro sem o
# campo NÃO zera um valor já persistido. tipo_veiculo é NOT NULL (sempre presente).
CAMPOS_COALESCE = ["modelo", "ano", "secretaria"]
# km_atual NÃO é atualizado pelo cadastro: monotonic-exclude (ADR-005; só o R10 o eleva, R4).
 

def carregar_cadastro(engine: Engine) -> dict:
    """Upsert do cadastro de data/seeds/veiculos.json (R4). Pulado por hash (R1).
    Retorna resumo do contrato {situacao, extraidos, consolidados, rejeitados}."""
    
    caminho = cadastro_veiculos()
    identificador = str(caminho)
    hash12 = sha256_conteudo(caminho.read_bytes())
    if fonte_ja_vista(engine, "veiculo", hash12):
        return {"situacao": "sem_novidade", "extraidos": 0, "consolidados": 0, "rejeitados": 0}
    
    fonte_origem = montar_fonte_origem(identificador, hash12)
    veiculos = json.loads(caminho.read_text())

    ins = dialeto_insert(engine)
    # list[dict] para bulk insert 
    stmt = ins(Veiculo.__table__).values([_linha(v, fonte_origem) for v in veiculos])
    # do_update por placa (PK); km_atual intocado no update (R4).

    # tipo_veiculo (NOT NULL): last-write-wins direto. modelo/ano/secretaria (anuláveis):
    # coalesce-preserva-não-nulo. fonte_origem: last-write-wins (proveniência). ADR-005.
    set_ = {"tipo_veiculo": stmt.excluded.tipo_veiculo, "fonte_origem": stmt.excluded.fonte_origem}
    for c in CAMPOS_COALESCE:
        set_[c] = func.coalesce(getattr(stmt.excluded, c), getattr(Veiculo, c))
    stmt = stmt.on_conflict_do_update(index_elements=["placa"], set_=set_)
    
    with engine.begin() as conn:
        conn.execute(stmt)

    # cada linha do JSON insere ou atualiza a sua placa (rowcount é -1 no psycopg
    # em INSERT multi-VALUES — não confiar nele)
    return {
        "situacao": "ok",
        "extraidos": len(veiculos),
        "consolidados": len(veiculos),
        "rejeitados": 0,
    }

def _linha(v: dict, fonte_origem: str) -> dict:
    return {
        "placa": v["placa"],
        "tipo_veiculo": v["tipo_veiculo"],
        "modelo": v.get("modelo"),
        "ano": v.get("ano"),
        "secretaria": v.get("secretaria"),
        "km_atual": v.get("km_atual", 0),   # baseline inicial; update não o toca (R4)
        "fonte_origem": fonte_origem,
    }