import json
from datetime import datetime
 
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
 
from db.models import LogQualidade

def dialeto_insert(engine: Engine):
    """
    Fábrica de INSERT por dialeto (R3): retorna sqlite.insert ou postgresql.insert,
    para uso com on_conflict_do_nothing / on_conflict_do_update.
    """
    return sqlite_insert if engine.dialect.name == "sqlite" else pg_insert

def gravar_rejeicoes(engine: Engine, fonte: str, rejeicoes: list[dict], carga_em: datetime) -> int:
    """Append de rejeições em log_qualidade (R7). Cada rejeicao é um dict com
    'registro_bruto' (dict | str) e 'motivo_rejeicao'. dict → JSON serializado;
    str → usada como-está (caso fonte_indisponivel, R8: classe+mensagem do erro).
    Retorna o número de linhas gravadas."""
    if not rejeicoes:
        return 0
    
    linhas = [
        {
            "fonte": fonte,
            "registro_bruto": (
                r["registro_bruto"]
                if isinstance(r["registro_bruto"], str)
                else json.dumps(r["registro_bruto"], ensure_ascii=False, default=str)
            ),
            "motivo_rejeicao": r["motivo_rejeicao"],
            "carga_em": carga_em,
        }
        for r in rejeicoes
    ]
    with engine.begin() as conn:
        conn.execute(insert(LogQualidade.__table__), linhas)
    return len(linhas)