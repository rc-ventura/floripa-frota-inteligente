"""Regras puras de disparo do motor (spec 004) — sem banco, sem I/O.

Separadas de `alertas/motor.py` para serem testáveis em isolamento (T005) e para deixar
o laço do motor legível: o motor lê o estado consolidado e delega a **decisão** a estas
funções. Correspondem à arquitetura §5.1 e à decisão de pesquisa R5.
"""


def km_confiavel(km_atual: int | None, km_no_momento: int | None) -> bool:
    """R5 — o km é confiável para avaliar o gatilho por km quando:
    há leitura atual positiva, há km registrado na última manutenção e o odômetro não
    andou para trás (`km_atual >= km_no_momento`, ADR-002). Qualquer violação torna o km
    não confiável → o motor emite `dados_insuficientes` em vez de arriscar um alerta falso.
    """
    return (
        km_atual is not None
        and km_atual > 0
        and km_no_momento is not None
        and km_atual >= km_no_momento
    )


def dispara_km(km_desde: int, limite_km: int, antecedencia_km: int) -> bool:
    """Gatilho por km (arquitetura §5.1): dispara quando o rodado desde a última
    manutenção alcança o limite descontada a antecedência."""
    return km_desde >= limite_km - antecedencia_km


def dispara_tempo(dias_desde: int, limite_dias: int, antecedencia_dias: int) -> bool:
    """Gatilho por tempo (arquitetura §5.1): dispara quando os dias desde a última
    manutenção alcançam o limite descontada a antecedência."""
    return dias_desde >= limite_dias - antecedencia_dias
