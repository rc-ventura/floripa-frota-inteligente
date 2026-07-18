"""Helpers de extração: novidade por hash (R1) e lote por carga (R2)."""
import hashlib
from datetime import datetime
 
from sqlalchemy import text
from sqlalchemy.engine import Engine

def sha256_conteudo(conteudo: bytes) -> str:
    """
    SHA-256 do conteúdo → 12 primeiros hex (R1).
    """
    return hashlib.sha256(conteudo).hexdigest()[:12]

def montar_fonte_origem(identificador: str, hash12: str) -> str:
    """
    <identificador>@sha256:<12hex> (R1, contrato ciclo_pipeline.md § fonte_origem).
    """
    return f"{identificador}@sha256:{hash12}"

def fonte_ja_vista(engine: Engine, tabela: str, hash12: str) -> bool:
    """
    True se o hash já existe em <tabela>.fonte_origem (R1). Funciona para stg_* e
    para veiculo (R4 — cadastro sem staging). {tabela} nao eh enviado pelo usuario.
    """
    with engine.connect() as conn:
        sql = text(f"SELECT 1 FROM {tabela} WHERE fonte_origem LIKE :padrao LIMIT 1")
        row = conn.execute(sql, {"padrao": f"%sha256:{hash12}"}).first()
        return row is not None


def novo_lote() -> datetime:
    """Carimbo de carga único por fonte/ciclo (R2). Timestamp do início da extração."""
    return datetime.now()