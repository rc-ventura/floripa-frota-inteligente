import os
 
DEFAULT_CICLO_INTERVALO_SEGUNDOS = 90
 
 
def intervalo_ciclo_segundos() -> int:
    """Intervalo entre ciclos completos (ETL → Motor), em segundos.
    Lê `CICLO_INTERVALO_SEGUNDOS` do ambiente; default 90."""
    try:
        v = int(os.environ.get("CICLO_INTERVALO_SEGUNDOS", DEFAULT_CICLO_INTERVALO_SEGUNDOS))
    except (TypeError, ValueError):
        return DEFAULT_CICLO_INTERVALO_SEGUNDOS
    return v if v > 0 else DEFAULT_CICLO_INTERVALO_SEGUNDOS
