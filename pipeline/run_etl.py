import logging
import sys
 
from db.config import get_engine
from pipeline.extract.abastecimento import extrair_abastecimento
from pipeline.extract.licenciamento import extrair_licenciamento
from pipeline.extract.manutencao import extrair_manutencao
from pipeline.extract.multas import extrair_multas
from pipeline.load.cadastro import carregar_cadastro
from pipeline.load.upsert import (
    gravar_rejeicoes, upsert_abastecimento, upsert_licenciamento,
    upsert_manutencao, upsert_multa,
)
from pipeline.transform.qualidade import (
    transformar_abastecimento, transformar_licenciamento,
    transformar_manutencao, transformar_multas,
)
logger = logging.getLogger("pipeline")

# fontes de eventos em sequência fixa (
_FONTES = [
    ("abastecimento", extrair_abastecimento, transformar_abastecimento, upsert_abastecimento),
    ("multas", extrair_multas, transformar_multas, upsert_multa),
    ("manutencao", extrair_manutencao, transformar_manutencao, upsert_manutencao),
    ("licenciamento", extrair_licenciamento, transformar_licenciamento, upsert_licenciamento),
]

def executar_ciclo() -> dict:
    """E→T→L das 4 fontes + cadastro. Retorna resumo por fonte (contrato § Retorno).
 
    Cadastro primeiro (R4). Cada fonte: extrai staging → transforma (só o lote
    corrente, R2) → carrega (upsert idempotente R3) + rejeições em log_qualidade.
    """

    engine = get_engine()
    resumo: dict = {}

    # Cadastro primeiro: todas as FKs e tipo_veiculo (NOT NULL) dependem dele (R4).
    resumo["cadastro"] = carregar_cadastro(engine)

    # 4 fontes de eventos. Estágios Extract/Transform/Load são ligados em T015/T020.
    for nome, extrair, transformar, upsert in _FONTES:
        resumo[nome] = _processar_fonte(engine, nome, extrair, transformar, upsert)

    return resumo

def _processar_fonte(engine, nome, extrair, transformar, carregar) -> dict:
    """E→T→L de uma fonte. Se extraidos == 0 (sem_novidade), pula T→L (R1/R2)."""

    resumo = extrair(engine)
    # carga_em identifica o lote (interno — não faz parte do resumo do contrato)
    carga_em = resumo.pop("carga_em", None)
    if resumo["extraidos"] == 0:
        return resumo  # sem_novidade — nada a transformar

    validos, rejeicoes = transformar(engine, carga_em)
    resumo["consolidados"] = carregar(engine, validos)
    resumo["rejeitados"] = gravar_rejeicoes(engine, nome, rejeicoes, carga_em)
    return resumo
 

def _imprimir_resumo(resumo: dict) -> None:
    for fonte, r in resumo.items():
        print(f"{fonte:14s} {r['situacao']:12s} "
              f"extraidos={r['extraidos']} consolidados={r['consolidados']} rejeitados={r['rejeitados']}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        _imprimir_resumo(executar_ciclo())
    except Exception as e:  # erro estrutural: banco inacessível, esquema ausente
        logger.error("erro estrutural: %s", e, exc_info=True)
        sys.exit(1)
    sys.exit(0)  # exit 0 mesmo com fonte indisponível (T026); ≠0 só em erro estrutural
