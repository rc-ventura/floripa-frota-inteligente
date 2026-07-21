from sqlalchemy import Engine, update
 
from db.config import get_engine
from db.models import Alerta

def resolver_alerta(engine: Engine | None, alerta_id: int) -> bool:
    """Marca um alerta como `resolvido` (permanece no histórico — FR-004).
    Retorna True se uma linha foi afetada, False se o id não existe."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            update(Alerta.__table__)
            .where(Alerta.id == alerta_id)
            .values(situacao="resolvido")
        )
        return result.rowcount == 1