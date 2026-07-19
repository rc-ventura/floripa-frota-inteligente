import logging
import sys
 
from db.config import get_engine
from pipeline.extract.abastecimento import extrair_abastecimento
from pipeline.extract.licenciamento import extrair_licenciamento
from pipeline.extract.manutencao import extrair_manutencao
from pipeline.extract.multas import extrair_multas
from pipeline.load.cadastro import carregar_cadastro
 
logger = logging.getLogger("pipeline")

# fontes de eventos em sequência fixa (
_FONTES_EVENTOS = [
    ("abastecimento", extrair_abastecimento),
    ("multas", extrair_multas),
    ("manutencao", extrair_manutencao),
    ("licenciamento", extrair_licenciamento),
]

def executar_ciclo() -> dict:
    """E→T→L das 4 fontes + cadastro. Cadastro primeiro (FK + tipo_veiculo NOT NULL — R4);
    ordem das 4 fontes é fixa (irrelevante entre si, fixada por determinismo de teste).
    Retorna resumo por fonte (contrato § Retorno)."""

    engine = get_engine()
    resumo: dict = {}

    # Cadastro primeiro: todas as FKs e tipo_veiculo (NOT NULL) dependem dele (R4).
    resumo["cadastro"] = carregar_cadastro(engine)

    # 4 fontes de eventos. Estágios Extract/Transform/Load são ligados em T015/T020.
    for nome, extrair in _FONTES_EVENTOS:
        resumo[nome] = extrair(engine)

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
