import logging
import sys
 
from db.config import get_engine
from pipeline.extract import novo_lote
from pipeline.load.cadastro import carregar_cadastro
 
logger = logging.getLogger("pipeline")

def executar_ciclo() -> dict:
    """E→T→L das 4 fontes + cadastro. Cadastro primeiro (FK + tipo_veiculo NOT NULL — R4);
    ordem das 4 fontes é fixa (irrelevante entre si, fixada por determinismo de teste).
    Retorna resumo por fonte (contrato § Retorno)."""

    engine = get_engine()
    resumo: dict = {}

    # Cadastro primeiro: todas as FKs e tipo_veiculo (NOT NULL) dependem dele (R4).
    resumo["cadastro"] = carregar_cadastro(engine)

    # 4 fontes de eventos. Estágios Extract/Transform/Load são ligados em T015/T020.
    for nome, processar in [
       ("abastecimento", _processar_abastecimento),
        ("multas", _processar_multas),
        ("manutencao", _processar_manutencao),
        ("licenciamento", _processar_licenciamento),
    ]:
        carga_em = novo_lote()
        resumo[nome] = processar(engine, carga_em)
    return resumo


def _resumo_zero(situacao: str = "sem_novidade") -> dict:
    return {"situacao": situacao, "extraidos": 0, "consolidados": 0, "rejeitados": 0}
 

# --- Stubs das 4 fontes (substituídos em T011–T014 · T015 · T020) ---
 
def _processar_abastecimento(engine, carga_em) -> dict:
    return _resumo_zero()  # TODO T011/T015/T020
 
def _processar_multas(engine, carga_em) -> dict:
    return _resumo_zero()  # TODO T012/T015/T020
 
def _processar_manutencao(engine, carga_em) -> dict:
    return _resumo_zero()  # TODO T013/T015/T020
 
def _processar_licenciamento(engine, carga_em) -> dict:
    return _resumo_zero()  # TODO T014/T015/T020
    

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
