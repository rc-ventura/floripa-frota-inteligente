from datetime import date
 
from sqlalchemy import select
from sqlalchemy.engine import Engine
 
from db.models import (
    StgAbastecimento, StgLicenciamento, StgManutencao, StgMultas, Veiculo,
)
from pipeline.transform.normalizadores import (
    converter_decimal, converter_int, interpretar_data,
    normalizar_categoria, normalizar_placa, normalizar_situacao, normalizar_tipo_manutencao,
)
 
SITUACOES_MULTAS = {"pendente", "paga"}
SITUACOES_LICENCIAMENTO = {"em_dia", "vencido"}

def _rejeitar(registro_bruto: dict, motivo: str) -> dict:
    """Empacota uma rejeição no formato esperado por gravar_rejeicoes."""
    return {"registro_bruto": registro_bruto,"motivo_rejeicao": motivo}

def _placas_conhecidas(engine: Engine) -> set[str]:
    """Conjunto de placas canônicas no cadastro (para checagem veiculo_desconhecido — R4).
    Chamado após o cadastro ser carregado (sempre primeiro no ciclo)."""
    with engine.connect() as conn:
        return {r[0] for r in conn.execute(select(Veiculo.placa)).fetchall()}

def _bruto(row: dict) -> dict:
    """Extrai o registro bruto do staging Row como dict (para log_qualidade)."""
    return dict(row._mapping)

# ---------- Fonte 1 — Abastecimento ----------

def transformar_abastecimento(engine: Engine, carga_em: date) -> tuple[list[dict], list[dict]]:
    """Staging → consolidada abastecimento. Chave de dedup: (placa, data, km);
    km NULL não colide (ADR-004 caminho 2) — cada row sem km é única."""
    
    conhecidas = _placas_conhecidas(engine)

    with engine.connect() as conn:
        rows = conn.execute(
            select(StgAbastecimento).where(StgAbastecimento.carga_em == carga_em)
        ).fetchall()
 
    candidatos: list[tuple[dict, dict]] = []
    rejeicoes: list[dict] = []

    for row in rows:
        bruto = _bruto(row)
        # 1. Placa
        placa = normalizar_placa(row.placa)
        if placa is None:
            rejeicoes.append(_rejeitar(bruto, "placa_invalida")); continue
        if placa not in conhecidas:
            rejeicoes.append(_rejeitar(bruto, "veiculo_desconhecido")); continue
        # 2. Data (NOT NULL)
        if not row.data or not row.data.strip():
            rejeicoes.append(_rejeitar(bruto, "data_ausente")); continue
        data = interpretar_data(row.data)
        if data is None:
            rejeicoes.append(_rejeitar(bruto, "data_invalida")); continue
        # 3. Litros (nullable, mas se presente deve ser válido)
        litros = converter_decimal(row.litros)
        if row.litros and row.litros.strip() and litros is None:
            rejeicoes.append(_rejeitar(bruto, "valor_invalido")); continue
        # 4. Valor (nullable, mas se presente deve ser válido)
        valor = converter_decimal(row.valor)
        if row.valor and row.valor.strip() and valor is None:
            rejeicoes.append(_rejeitar(bruto, "valor_invalido")); continue
        # 5. km (nullable — ausente é válido, ADR-002; presente e inválido → valor_invalido)
        km = converter_int(row.km)
        if row.km and row.km.strip() and km is None:
            rejeicoes.append(_rejeitar(bruto, "valor_invalido")); continue
 
        candidatos.append(({
            "placa": placa, "data": data, "litros": litros, "valor": valor,
            "km_hodometro": km, "condutor_pseudo": row.condutor,
            "fonte_origem": row.fonte_origem,
        }, bruto))
 
    # Dedup intra-lote: (placa, data, km); km NULL não colide (ADR-004)
    chaves: set = set()
    validos: list[dict] = []
    for valido, bruto in candidatos:
        km = valido["km_hodometro"]
        if km is not None:
            chave = (valido["placa"], valido["data"], km)
            if chave in chaves:
                rejeicoes.append(_rejeitar(bruto, "duplicado")); continue
            chaves.add(chave)
        validos.append(valido)  # km None → sempre entra (NULL≠NULL)
 
    return validos, rejeicoes
 
 # ---------- Fonte 2 — Multas ----------

def transformar_multas(engine: Engine, carga_em) -> tuple[list[dict], list[dict]]:
    """Staging → consolidada multa. Descarta cnh/gravidade/codigo_infracao (FR-011/LGPD).
    Chave de dedup: (placa, data, valor, coalesce(condutor,'')) — espelha ux_multa_upsert."""
    
    conhecidas = _placas_conhecidas(engine)
    
    with engine.connect() as conn:
        rows = conn.execute(
            select(StgMultas).where(StgMultas.carga_em == carga_em)
        ).fetchall()
 
    candidatos: list[tuple[dict, dict]] = []
    rejeicoes: list[dict] = []

    for row in rows:
        bruto = _bruto(row)
        # 1. Placa (minúsculas na fonte → normaliza)
        placa = normalizar_placa(row.placa)
        if placa is None:
            rejeicoes.append(_rejeitar(bruto, "placa_invalida")); continue
        if placa not in conhecidas:
            rejeicoes.append(_rejeitar(bruto, "veiculo_desconhecido")); continue
        # 2. Data
        if not row.data or not row.data.strip():
            rejeicoes.append(_rejeitar(bruto, "data_ausente")); continue
        data = interpretar_data(row.data)
        if data is None:
            rejeicoes.append(_rejeitar(bruto, "data_invalida")); continue
        # 3. Valor (NOT NULL na consolidada)
        valor = converter_decimal(row.valor)
        if valor is None:
            rejeicoes.append(_rejeitar(bruto, "valor_invalido")); continue
        # 4. Situação (NOT NULL, CHECK)
        situacao = normalizar_situacao(row.situacao, SITUACOES_MULTAS)
        if situacao is None:
            rejeicoes.append(_rejeitar(bruto, "situacao_desconhecida")); continue
        # cnh/gravidade/codigo_infracao: DESCARTADOS (FR-011) — não entram no dict
 
        candidatos.append(({
            "placa": placa, "data": data, "valor": valor,
            "condutor_pseudo": row.condutor, "situacao": situacao,
            "fonte_origem": row.fonte_origem,
        }, bruto))
 
    # Dedup intra-lote: espelha ux_multa_upsert (placa, data, valor, coalesce(condutor,''))
    chaves: set = set()
    validos: list[dict] = []
    for valido, bruto in candidatos:
        chave = (valido["placa"], valido["data"], valido["valor"],
                 valido["condutor_pseudo"] or "")
        if chave in chaves:
            rejeicoes.append(_rejeitar(bruto, "duplicado")); continue
        chaves.add(chave)
        validos.append(valido)
 
    return validos, rejeicoes
 
 
# ---------- Fonte 3 — Manutenção ----------

# ---------- Fonte 3 — Manutenção ----------
 
 
def transformar_manutencao(engine: Engine, carga_em) -> tuple[list[dict], list[dict]]:
    """Staging → consolidada manutencao. Vocabulários R6 (tipo, categoria).
    Chave de dedup: (placa, data, tipo)."""
    conhecidas = _placas_conhecidas(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            select(StgManutencao).where(StgManutencao.carga_em == carga_em)
        ).fetchall()
 
    candidatos: list[tuple[dict, dict]] = []
    rejeicoes: list[dict] = []
 
    for row in rows:
        bruto = _bruto(row)
        # 1. Placa (canônica na fonte, mas normaliza por defesa em profundidade)
        placa = normalizar_placa(row.placa)
        if placa is None:
            rejeicoes.append(_rejeitar(bruto, "placa_invalida")); continue
        if placa not in conhecidas:
            rejeicoes.append(_rejeitar(bruto, "veiculo_desconhecido")); continue
        # 2. Data (NOT NULL) — TEXT ISO ou serial Excel
        if not row.data or not str(row.data).strip():
            rejeicoes.append(_rejeitar(bruto, "data_ausente")); continue
        data = interpretar_data(row.data)
        if data is None:
            rejeicoes.append(_rejeitar(bruto, "data_invalida")); continue
        # 3. Tipo (NOT NULL, CHECK) — vocabulário R6
        tipo = normalizar_tipo_manutencao(row.tipo)
        if tipo is None:
            rejeicoes.append(_rejeitar(bruto, "tipo_desconhecido")); continue
        # 4. Categoria (NOT NULL, CHECK) — vocabulário R6
        categoria = normalizar_categoria(row.categoria)
        if categoria is None:
            rejeicoes.append(_rejeitar(bruto, "categoria_desconhecida")); continue
        # 5. km_no_momento (nullable — ausente é válido)
        km = converter_int(row.km_no_momento)
        if row.km_no_momento and str(row.km_no_momento).strip() and km is None:
            rejeicoes.append(_rejeitar(bruto, "valor_invalido")); continue
        # 6. Valor (nullable, mas se presente deve ser válido)
        valor = converter_decimal(row.valor)
        if row.valor and str(row.valor).strip() and valor is None:
            rejeicoes.append(_rejeitar(bruto, "valor_invalido")); continue
 
        candidatos.append(({
            "placa": placa, "data": data, "tipo": tipo, "categoria": categoria,
            "km_no_momento": km, "valor": valor,
            "fonte_origem": row.fonte_origem,
        }, bruto))
 
    # Dedup intra-lote: (placa, data, tipo)
    chaves: set = set()
    validos: list[dict] = []
    for valido, bruto in candidatos:
        chave = (valido["placa"], valido["data"], valido["tipo"])
        if chave in chaves:
            rejeicoes.append(_rejeitar(bruto, "duplicado")); continue
        chaves.add(chave)
        validos.append(valido)
 
    return validos, rejeicoes
 
 
# ---------- Fonte 4 — Licenciamento ----------

def transformar_licenciamento(engine: Engine, carga_em) -> tuple[list[dict], list[dict]]:
    """Staging → consolidada licenciamento. Dedup por placa mantendo vencimento mais
    recente (R3); preterida → log_qualidade com motivo 'duplicado'."""
    conhecidas = _placas_conhecidas(engine)
    with engine.connect() as conn:
        rows = conn.execute(
            select(StgLicenciamento).where(StgLicenciamento.carga_em == carga_em)
        ).fetchall()
 
    candidatos: list[tuple[dict, dict]] = []
    rejeicoes: list[dict] = []
 
    for row in rows:
        bruto = _bruto(row)
        # 1. Placa
        placa = normalizar_placa(row.placa)
        if placa is None:
            rejeicoes.append(_rejeitar(bruto, "placa_invalida")); continue
        if placa not in conhecidas:
            rejeicoes.append(_rejeitar(bruto, "veiculo_desconhecido")); continue
        # 2. Vencimento (nullable — ausente é válido)
        vencimento = interpretar_data(row.vencimento)
        if row.vencimento and str(row.vencimento).strip() and vencimento is None:
            rejeicoes.append(_rejeitar(bruto, "data_invalida")); continue
        # 3. Situação (nullable — ausente é válido; se presente, deve estar no CHECK)
        situacao = normalizar_situacao(row.situacao, SITUACOES_LICENCIAMENTO)
        if row.situacao and row.situacao.strip() and situacao is None:
            rejeicoes.append(_rejeitar(bruto, "situacao_desconhecida")); continue
 
        candidatos.append(({
            "placa": placa, "vencimento": vencimento, "situacao": situacao,
            "fonte_origem": row.fonte_origem,
        }, bruto))
 
    # Dedup por placa: manter vencimento mais recente; preterida → duplicado
    por_placa: dict[str, list[tuple[dict, dict]]] = {}
    for valido, bruto in candidatos:
        por_placa.setdefault(valido["placa"], []).append((valido, bruto))
 
    validos: list[dict] = []
    for _p, grupo in por_placa.items():
        # Mais recente primeiro; None vencimento → date.min (último)
        grupo.sort(key=lambda x: x[0]["vencimento"] or date.min, reverse=True)
        validos.append(grupo[0][0])
        for _v, bruto in grupo[1:]:
            rejeicoes.append(_rejeitar(bruto, "duplicado"))
 
    return validos, rejeicoes