import logging
import sys
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from alertas.regras import dispara_km, dispara_tempo, km_confiavel
from db.config import get_engine
from db.models import Alerta, LimiarConfig, Manutencao, Veiculo

logger = logging.getLogger(__name__)

# ---------- helpers de dialeto (duplicado de pipeline/load/upsert.py de propósito:
# FR-007 proíbe o motor de importar pipeline.* — fronteira de camada) ----------

def _dialeto_insert(engine: Engine):
    """Fábrica de INSERT por dialeto: sqlite.insert ou postgresql.insert."""
    return sqlite_insert if engine.dialect.name == "sqlite" else pg_insert


# ---------- leituras (SEM cache — SC-002) ----------

def _carregar_limiares(engine: Engine) -> dict[tuple[str, str], Any]:
    """Lê `LIMIAR_CONFIG` a cada chamada (sem cache de processo — SC-002).
    Retorna dict keyed por (tipo_veiculo, tipo_manutencao) -> Row."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                LimiarConfig.id,
                LimiarConfig.tipo_veiculo,
                LimiarConfig.tipo_manutencao,
                LimiarConfig.limite_km,
                LimiarConfig.limite_dias,
                LimiarConfig.antecedencia_km,
                LimiarConfig.antecedencia_dias,
            )
        ).all()
    return {(r.tipo_veiculo, r.tipo_manutencao): r for r in rows}


def _carregar_veiculos(engine: Engine) -> list[Any]:
    """Lista todos os veículos com tipo + km_atual (insumos do motor)."""
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(
                    Veiculo.placa,
                    Veiculo.tipo_veiculo,
                    Veiculo.km_atual,
                )
            ).all()
        )


def _carregar_ultimas_manutencoes(engine: Engine) -> dict[tuple[str, str], Any]:
    """Última manutenção por (placa, tipo) — usa o índice ix_manutencao_placa_tipo_data.
    Lê via ORM (não texto cru) para que `data` volte como `date` nos dois dialetos;
    a UniqueConstraint(placa, data, tipo) garante que não há empate em MAX(data)."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                Manutencao.placa,
                Manutencao.tipo,
                Manutencao.data,
                Manutencao.km_no_momento,
            )
        ).all()
    ultimas: dict[tuple[str, str], Any] = {}
    for r in rows:
        chave = (r.placa, r.tipo)
        atual = ultimas.get(chave)
        if atual is None or r.data > atual.data:
            ultimas[chave] = r
    return ultimas


# ---------- inserção idempotente ----------

def _inserir_alertas(engine: Engine, alertas: list[dict]) -> dict[str, int]:
    """INSERT idempotente por `tipo_gatilho` — ON CONFLICT DO NOTHING captura
    `ux_alerta_ativo` (FR-003). Retorna {tipo_gatilho: criados} por delta de COUNT
    (não rowcount: psycopg devolve -1 em multi-VALUES com ON CONFLICT — learning lesson
    2026-07-19). Agrupa por tipo para as contagens `criados_*` do contrato § Retorno.
    `engine.begin()` garante o COMMIT — sem ele os alertas não persistem (SQLAlchemy 2.0
    future não faz autocommit)."""

    if not alertas:
        return {}
    ins = _dialeto_insert(engine)
    por_tipo: dict[str, list[dict]] = defaultdict(list)
    for a in alertas:
        por_tipo[a["tipo_gatilho"]].append(a)

    criados: dict[str, int] = {}
    with engine.begin() as conn:
        for tipo, linhas in por_tipo.items():
            antes = conn.execute(select(func.count()).select_from(Alerta.__table__)).scalar()
            conn.execute(ins(Alerta.__table__).values(linhas).on_conflict_do_nothing())
            depois = conn.execute(select(func.count()).select_from(Alerta.__table__)).scalar()
            criados[tipo] = depois - antes
    return criados


# ---------- núcleo do motor ----------
def verificar_alertas(engine: Engine | None = None, hoje: date | None = None) -> dict:
    """Avalia todos os veículos × tipos aplicáveis e insere alertas em `ALERTA`.

    Lê `LIMIAR_CONFIG` a cada chamada (sem cache — SC-002). Comunica-se só via banco
    (FR-007). Idempotente (FR-003) — `ux_alerta_ativo` rejeita duplicata de alerta
    ativo. Motor é *create-only* — nunca resolve (FR-004). `hoje` é injetável para
    determinismo dos testes (contrato § Invocação).

    Returns (contrato § Retorno — dicionário de diagnóstico):
        `veiculos_avaliados` (veículos percorridos na verificação), `criados_km`,
        `criados_tempo`, `criados_dados_insuficientes` (novos alertas de cada tipo
        inseridos neste ciclo) e `ja_ativos` (candidatos que colidiram com alerta
        ativo existente — no-op idempotente).
    """
    engine = engine or get_engine()
    hoje = hoje or date.today()
    agora = datetime.now()

    limiares = _carregar_limiares(engine)
    veiculos = _carregar_veiculos(engine)
    ultimas = _carregar_ultimas_manutencoes(engine)

    a_inserir: list[dict] = []

    for veic in veiculos:
        tipos_aplicaveis = [
            tipo for (tv, tipo) in limiares if tv == veic.tipo_veiculo
        ]
        # Veículo sem nenhum tipo aplicável → dados_insuficientes (edge case da spec)
        if not tipos_aplicaveis:
            a_inserir.append({
                "placa": veic.placa,
                "limiar_id": None,
                "tipo_gatilho": "dados_insuficientes",
                "gerado_em": agora,
                "situacao": "ativo",
                "detalhe": f"sem limiar configurado para {veic.tipo_veiculo}",
            })
            continue

        impedimentos_veic: list[str] = []

        for tipo in tipos_aplicaveis:
            limiar = limiares[(veic.tipo_veiculo, tipo)]
            ultima = ultimas.get((veic.placa, tipo))

            # Sem manutenção registrada do tipo
            if ultima is None:
                impedimentos_veic.append(f"sem manutencao de {tipo}")
                continue

            # Gatilho por tempo (sempre avaliável — data é NOT NULL)
            dias_desde = (hoje - ultima.data).days
            if dispara_tempo(dias_desde, limiar.limite_dias, limiar.antecedencia_dias):
                a_inserir.append({
                    "placa": veic.placa,
                    "limiar_id": limiar.id,
                    "tipo_gatilho": "tempo",
                    "gerado_em": agora,
                    "situacao": "ativo",
                    "detalhe": (
                        f"{tipo}: dias_desde_ultima={dias_desde}, "
                        f"limite={limiar.limite_dias}, "
                        f"antecedencia={limiar.antecedencia_dias}"
                    ),
                })

            # Gatilho por km (só com km confiável — R5); senão vira impedimento (ADR-002)
            if km_confiavel(veic.km_atual, ultima.km_no_momento):
                km_desde = veic.km_atual - ultima.km_no_momento
                if dispara_km(km_desde, limiar.limite_km, limiar.antecedencia_km):
                    a_inserir.append({
                        "placa": veic.placa,
                        "limiar_id": limiar.id,
                        "tipo_gatilho": "km",
                        "gerado_em": agora,
                        "situacao": "ativo",
                        "detalhe": (
                            f"{tipo}: km_desde_ultima={km_desde}, "
                            f"limite={limiar.limite_km}, "
                            f"antecedencia={limiar.antecedencia_km}"
                        ),
                    })
            else:
                impedimentos_veic.append(
                    f"km não confiável para {tipo} "
                    f"(km_atual={veic.km_atual}, km_no_momento={ultima.km_no_momento})"
                )

        # 1 dados_insuficientes por veículo, agregando todos os impedimentos
        if impedimentos_veic:
            a_inserir.append({
                "placa": veic.placa,
                "limiar_id": None,
                "tipo_gatilho": "dados_insuficientes",
                "gerado_em": agora,
                "situacao": "ativo",
                "detalhe": "; ".join(impedimentos_veic),
            })

    criados = _inserir_alertas(engine, a_inserir)
    criados_km = criados.get("km", 0)
    criados_tempo = criados.get("tempo", 0)
    criados_di = criados.get("dados_insuficientes", 0)
    # candidatos que não entraram colidiram com um alerta ativo (no-op idempotente):
    # não há colisão intra-lote (cada (placa, tipo_gatilho, limiar) é único no ciclo)
    ja_ativos = len(a_inserir) - (criados_km + criados_tempo + criados_di)

    return {
        "veiculos_avaliados": len(veiculos),
        "criados_km": criados_km,
        "criados_tempo": criados_tempo,
        "criados_dados_insuficientes": criados_di,
        "ja_ativos": ja_ativos,
    }


# ---------- CLI (python -m alertas.motor) ----------

def _imprimir_resumo(resumo: dict) -> None:
    print(
        f"veiculos_avaliados={resumo['veiculos_avaliados']} "
        f"criados_km={resumo['criados_km']} "
        f"criados_tempo={resumo['criados_tempo']} "
        f"criados_dados_insuficientes={resumo['criados_dados_insuficientes']} "
        f"ja_ativos={resumo['ja_ativos']}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        _imprimir_resumo(verificar_alertas())
    except Exception as e:  # erro estrutural: banco inacessível, esquema ausente
        logger.error("erro estrutural: %s", e, exc_info=True)
        sys.exit(1)
    sys.exit(0)  # exit 0 mesmo com 0 alertas criados; ≠0 só em erro estrutural
