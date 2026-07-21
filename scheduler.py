import logging
import signal
import sys
from datetime import datetime
 
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
 
from alertas.alert_config import intervalo_ciclo_segundos
from alertas.motor import verificar_alertas
from pipeline.run_etl import executar_ciclo
 
logger = logging.getLogger("scheduler")

def executar_ciclo_e_verificar(hoje=None) -> dict:
    """Ciclo único ordenado: ETL primeiro, motor depois (arquitetura §8).
 
    1. `executar_ciclo()` (spec 003) — extrai/transforma/carrega as 4 fontes + cadastro.
       Idempotente e resiliente (fonte fora do ar → `fonte_indisponivel` em log_qualidade,
       demais seguem — SC-005 da spec 003).
    2. `verificar_alertas()` (spec 004) — avalia o estado consolidado após a carga e
       insere alertas. Idempotente (FR-003), create-only (FR-004), só via banco (FR-007).
 
    `hoje` é injetável (repassado ao motor) para determinismo dos testes — em produção
    usa `date.today()`.
 
    Returns:
        dict com `etl` (resumo por fonte do contrato 003) e `motor` (resumo do contrato 004).
    """

    resumo_etl = executar_ciclo()
    resumo_motor = verificar_alertas(hoje=hoje) 
    logger.info(
        "ciclo completo: etl=%s motor=%s",
        {f: r.get("situacao") for f, r in resumo_etl.items()},
        resumo_motor,
    )
    return {"etl": resumo_etl, "motor": resumo_motor}

def main() -> None:
    """Sobe o BlockingScheduler com o ciclo único, intervalo por env var (SC-005).
 
    `max_instances=1` + `coalesce=True`: se um ciclo demorar mais que o intervalo, as
    execuções enfileiradas são coalescidas em uma (nunca sobrepõe — resiliência do
    upsert torna sobreposição inócua, mas não recomendada; contrato 003 § Concorrência).
    `next_run_time=now`: roda imediatamente na 1ª vez (não espera 1 intervalo).
    """

    intervalo = intervalo_ciclo_segundos()
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        executar_ciclo_e_verificar,
        trigger=IntervalTrigger(seconds=intervalo),
        id="ciclo_frota",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(),  # 1ª execução imediata
    )
    
    # Shutdown limpo em SIGINT (Ctrl-C) e SIGTERM (docker stop)
    def _shutdown(signum, frame):
        logger.info("sinal %s recebido — encerrando scheduler...", signum)
        scheduler.shutdown(wait=False)
 
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
 
    logger.info("scheduler iniciado: intervalo=%ss (CICLO_INTERVALO_SEGUNDOS)", intervalo)
    logger.info("Ctrl-C para encerrar")
    scheduler.start()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        main()
    except Exception as e:
        logger.error("erro estrutural: %s", e, exc_info=True)
        sys.exit(1)