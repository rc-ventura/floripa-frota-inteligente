import json
from datetime import datetime
 
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import text as sql_text

from db.models import LogQualidade
from db.models import Abastecimento, Licenciamento, Manutencao, Multa


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


def atualizar_km_atual(engine: Engine, placas_afetadas: set[str]) -> int:
    """R10/FR-010: após o upsert de abastecimento, para cada placa afetada,
    km_atual ← MAX(km_hodometro) do consolidado, MAS só se superar o atual
    (nunca rebaixa — monotonicidade). SQL portável SQLite/Postgres.
 
    Correlaciona veiculo.placa na subquery — funciona em ambos os dialetos.
    Retorna o número de veículos efetivamente atualizados."""
    
    if not placas_afetadas:
        return 0
    
    sql = sql_text("""
        UPDATE veiculo
        SET km_atual = (
            SELECT MAX(km_hodometro)
            FROM abastecimento 
            WHERE placa = veiculo.placa AND km_hodometro IS NOT NULL
        )
        WHERE placa = :placa
        AND (
            SELECT MAX(km_hodometro)
            FROM abastecimento 
            WHERE placa = veiculo.placa AND km_hodometro IS NOT NULL
        ) > km_atual
    """)
    
    with engine.begin() as conn:
        n = 0
        for p in placas_afetadas:
            n += conn.execute(sql, {"placa": p}).rowcount
        return n


# ---------- Upserts por tabela (T019) ----------


def _insert_contando_delta(engine: Engine, tabela, stmt) -> int:
    """Executa o INSERT e devolve quantas linhas realmente entraram (delta de COUNT
    na mesma transação). rowcount não serve: psycopg devolve -1 em INSERT
    multi-VALUES com ON CONFLICT — dialeto-agnóstico, exato para do_nothing."""
    with engine.begin() as conn:
        antes = conn.execute(select(func.count()).select_from(tabela)).scalar()
        conn.execute(stmt)
        return conn.execute(select(func.count()).select_from(tabela)).scalar() - antes


def upsert_abastecimento(engine: Engine, validos: list[dict]) -> int:
    """Fato: on_conflict_do_nothing() sem alvo (R3). Captura (placa, data, km_hodometro);
    km NULL não colide (ADR-004 caminho 2)."""
    if not validos:
        return 0
    ins = dialeto_insert(engine)
    stmt = ins(Abastecimento.__table__).values(validos).on_conflict_do_nothing()
    # delta, não rowcount: psycopg devolve -1 em multi-VALUES (learning lesson 2026-07-19)
    n = _insert_contando_delta(engine, Abastecimento.__table__, stmt)

    # R10: só placas com km_hodometro não-nulo podem elevar km_atual
    placas = {v["placa"] for v in validos if v.get("km_hodometro") is not None}
    atualizar_km_atual(engine, placas)
    return n


def upsert_manutencao(engine: Engine, validos: list[dict]) -> int:
    """Fato: on_conflict_do_nothing() sem alvo (R3). Captura (placa, data, tipo)."""
    if not validos:
        return 0
    ins = dialeto_insert(engine)
    stmt = ins(Manutencao.__table__).values(validos).on_conflict_do_nothing()
    return _insert_contando_delta(engine, Manutencao.__table__, stmt)


def upsert_multa(engine: Engine, validos: list[dict]) -> int:
    """Fato: on_conflict_do_nothing() SEM alvo (R3) — captura ux_multa_upsert
    (índice de expressão com coalesce, não endereçável como lista de colunas)."""
    if not validos:
        return 0
    ins = dialeto_insert(engine)
    stmt = ins(Multa.__table__).values(validos).on_conflict_do_nothing()
    return _insert_contando_delta(engine, Multa.__table__, stmt)


def upsert_licenciamento(engine: Engine, validos: list[dict]) -> int:
    """Dimensão: on_conflict_do_update por placa (R3). Atualiza vencimento, situacao,
    fonte_origem (vencimento mais recente vence — dedup do transform). Cada linha
    válida insere ou atualiza a sua placa → consolidados = len(validos)."""
    if not validos:
        return 0
    ins = dialeto_insert(engine)
    stmt = ins(Licenciamento.__table__).values(validos)
    # vencimento/situacao (anuláveis): coalesce-preserva-não-nulo — um lote com o campo
    # NULL NÃO zera o valor consolidado (ADR-005/Devin-B). fonte_origem: last-write-wins.
    stmt = stmt.on_conflict_do_update(
        index_elements=["placa"],
        set_={
            "vencimento": func.coalesce(stmt.excluded.vencimento, Licenciamento.vencimento),
            "situacao": func.coalesce(stmt.excluded.situacao, Licenciamento.situacao),
            "fonte_origem": stmt.excluded.fonte_origem,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)
    return len(validos)