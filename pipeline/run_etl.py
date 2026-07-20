import json
import logging
import sys
from datetime import datetime
 
from db.config import get_engine
from pipeline.extract.abastecimento import extrair_abastecimento
from pipeline.extract.licenciamento import extrair_licenciamento
from pipeline.extract.manutencao import extrair_manutencao
from pipeline.extract.multas import extrair_multas
from pipeline.extract import novo_lote
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
    """E→T→L de uma fonte, isolada por try/except (R8).
 
    Caminho feliz: extrai → se extraidos > 0, transforma → carrega + rejeições.
    Caminho sem_novidade: extrai → se extraidos == 0, pula T→L (R1/R2).
    Caminho falha: exceção → log_qualidade (fonte_indisponivel) + situacao=indisponivel,
    e o ciclo segue para a próxima fonte.
    """
    
    carga_em = novo_lote()
    try:
        resumo = extrair(engine)
        # pop ANTES de qualquer return: carga_em é canal interno e nunca pode
        # vazar para o resumo do contrato (nem no caminho sem_novidade)
        carga_em_lote = resumo.pop("carga_em", carga_em)
        if resumo["extraidos"] == 0:
            return resumo

        validos, rejeicoes = transformar(engine, carga_em_lote)
        resumo["consolidados"] = carregar(engine, validos)
        resumo["rejeitados"] = gravar_rejeicoes(engine, nome, rejeicoes, carga_em_lote)
        return resumo
    
    except Exception as exc:
    # R8: falha da fonte inteira → log_qualidade + logging.error, ciclo segue
        logger.error("fonte %s indisponível: %s", nome, exc, exc_info=True)
        descricao = f"{type(exc).__name__}: {exc}"
        gravar_rejeicoes(engine, nome, [{"registro_bruto": descricao,
                                          "motivo_rejeicao": "fonte_indisponivel"}], carga_em)
        return {"situacao": "indisponivel", "extraidos": 0,
                "consolidados": 0, "rejeitados": 1}

 

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
