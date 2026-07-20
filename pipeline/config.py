import os
from pathlib import Path

DEFAULT_INBOX = "data/inbox"
DEFAULT_MULTAS_API_URL = "http://localhost:8000"
DEFAULT_XLSX_MANUTENCAO = "data/seeds/manutencao.xlsx"
DEFAULT_SQLITE_LICENCIAMENTO = "data/seeds/licenciamento.sqlite"
DEFAULT_CADASTRO_VEICULOS = "data/seeds/veiculos.json"

def inbox_dir() -> Path:
    """Pasta monitortada de CSVs de abastecimento (Fonte 1)"""
    return Path(os.environ.get("PIPELINE_INBOX", DEFAULT_INBOX))

def multas_api_url() -> str:
    """Base URL da API multas (Fonte 2)"""
    return os.environ.get("MULTAS_API_URL", DEFAULT_MULTAS_API_URL)

def xlsx_manutencao() -> Path:
    """Planilha de manutencao, 3 abas (Fonte 3)"""
    return Path(os.environ.get("PIPELINE_XLSX_MANUTENCAO", DEFAULT_XLSX_MANUTENCAO))

def sqlite_licenciamento() -> Path:
    """Base legada de licenciamento, acesso somente-leitura (Fonte 4)."""
    return Path(os.environ.get("PIPELINE_SQLITE_LICENCIAMENTO", DEFAULT_SQLITE_LICENCIAMENTO))
 
 
def cadastro_veiculos() -> Path:
    """Cadastro canônico da frota — referência interna, carregado antes das 4 fontes (R4)."""
    return Path(os.environ.get("PIPELINE_CADASTRO_VEICULOS", DEFAULT_CADASTRO_VEICULOS))
