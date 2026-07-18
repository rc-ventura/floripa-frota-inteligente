import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from db.models import REGEX_PLACA_CANONICA   # ADR-001

_PLACA_RE = re.compile(REGEX_PLACA_CANONICA)


# Origem do serial Excel (research R5).
_ORIGEM_SERIAL = date(1899, 12, 30)
_SERIAL_MIN, _SERIAL_MAX = 20000, 80000
 

def normalizar_placa(valor: str | None) -> str | None:
    """Placa canônica ADR-001: maiúsculas, sem hífen/espaço; valida regex dual
    (antigo AAA9999 + Mercosul AAA9A99). None → placa_invalida em qualidade.py."""
    if not valor:
        return None
    s = str(valor).strip().upper().replace("-", "").replace(" ", "")
    return s if _PLACA_RE.match(s) else None

def interpretar_data(valor: str | None) -> date | None:
    """Parsing tolerante R5: (1) dd/mm/aaaa → (2) aaaa-mm-dd → (3) serial Excel
    20.000–80.000 (origem 1899-12-30). Ordem fixa, sem fuzzy.
    None/vazio → None (data_ausente); presente e não interpretável → None
    (data_invalida). A distinção do motivo cabe ao chamador (qualidade.py)."""
    if not valor:
        return None
    s = str(valor).strip()
    # (1) dd/mm/aaaa
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        pass
    # (2) aaaa-mm-dd
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        pass
    # (3) serial Excel
    if s.isdigit():
        n = int(s)
        if _SERIAL_MIN <= n <= _SERIAL_MAX:
            return _ORIGEM_SERIAL + timedelta(days=n)
    return None

def converter_decimal(valor: str | None) -> Decimal | None:
    """Vírgula→ponto, Decimal ≥ 0. None/vazio/inválido/negativo → None (valor_invalido)."""
    if not valor:
        return None
    s = str(valor).strip().replace(",", ".")
    if not s:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return d if d >= 0 else None

def converter_int(valor: str | None) -> int | None:
    """Inteiro ≥ 0. None/vazio → None (ausente, válido p/ km nullable); presente e
    não inteiro → None (valor_invalido). Distinção do motivo no chamador."""
    if valor is None:
        return None
    s = str(valor).strip()
    if not s:
        return None
    try:
        n = int(s)
    except ValueError:
        return None
    return n if n >= 0 else None

def _sem_acento(s: str) -> str:
    """Remove acentos """
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))

def _normalizar_texto(s: str) -> str:
    """casefold + sem acento + não-alfanum→espaço + colapso. Base de R6."""
    s = _sem_acento(s).casefold()
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())

def normalizar_tipo_manutencao(valor: str | None) -> str | None:
    """Vocabulário R6: oleo→troca_oleo, filtro→filtros, pneu→pneus, revisao→revisao_geral
    (inclui 'Revisão 10.000 km'). Sem correspondência → None (tipo_desconhecido)."""
    if not valor:
        return None
    s = _normalizar_texto(valor)
    if "oleo" in s:
        return "troca_oleo"
    if "filtro" in s:
        return "filtros"
    if "pneu" in s:
        return "pneus"
    if "revisao" in s:
        return "revisao_geral"
    return None

 
def normalizar_categoria(valor: str | None) -> str | None:
    """Vocabulário R6: prefixo prev→preventiva, corr→corretiva.
    Sem correspondência → None (categoria_desconhecida)."""
    if not valor:
        return None
    s = _normalizar_texto(valor)
    if s.startswith("prev"):
        return "preventiva"
    if s.startswith("corr"):
        return "corretiva"
    return None
 
 
def normalizar_situacao(valor: str | None, validos: set[str]) -> str | None:
    """Casefold + strip; pertence ao conjunto válido (CHECK do banco) → retorna;
    senão → None (situacao_desconhecida). O conjunto é passado por fonte (multas ≠
    licenciamento) — defesa em profundidade, não esperado (a fonte já padroniza)."""
    if valor is None:
        return None
    s = valor.strip().casefold()
    return s if s in validos else None