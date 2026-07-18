import json
 
from sqlalchemy.engine import Engine
 
from db.models import Veiculo
from pipeline.config import cadastro_veiculos
from pipeline.extract import fonte_ja_vista, montar_fonte_origem, sha256_conteudo
from pipeline.load.upsert import dialeto_insert

# Campos atualizados no conflito. km_atual NÃO está aqui: cadastro nunca o rebaixa
# (R4); só o R10 o eleva a partir de MAX(km_hodometro) do abastecimento.
CAMPOS_MUTAVEIS = ["tipo_veiculo", "modelo", "ano", "secretaria"]
 

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

    set_ = {c: getattr(stmt.excluded, c) for c in CAMPOS_MUTAVEIS}
    set_["fonte_origem"] = stmt.excluded.fonte_origem
    stmt = stmt.on_conflict_do_update(index_elements=["placa"], set_=set_)
    
    with engine.begin() as conn:
        result = conn.execute(stmt)
    
    return {
        "situacao": "ok", 
        "extraidos": len(veiculos), 
        "consolidados": result.rowcount, 
        "rejeitados": 0
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