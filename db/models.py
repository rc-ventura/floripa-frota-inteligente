
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import re
 
from sqlalchemy import (
    MetaData, String, Integer, Date, DateTime, Numeric, Text,
    ForeignKey, CheckConstraint, UniqueConstraint, Index, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, validates

REGEX_PLACA_CANONICA = r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"   # ADR-001
_PLACA_RE = re.compile(REGEX_PLACA_CANONICA)
 
_NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
 

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING)

class Veiculo(Base):
    __tablename__ = "veiculo"
    __table_args__ = (
        CheckConstraint("length(placa) = 7", name="placa_len"),
        CheckConstraint("tipo_veiculo IN ('leve','ambulancia','caminhao')", name="tipo_veiculo"),
    ) #check constraints de enum e formato de placas
    
    
    placa: Mapped[str] = mapped_column(String(7), primary_key=True)
    tipo_veiculo: Mapped[str] = mapped_column(String, nullable=False)
    modelo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ano: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    secretaria: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    km_atual: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    fonte_origem: Mapped[str] = mapped_column(String, nullable=False)

    # hook de validacao de formato de placa no objeto (ORM) 
    @validates("placa")
    def _chk_placa(self, _k, v):
        if not _PLACA_RE.match(v):
            raise ValueError(f"Placa fora do canônico ADR-001: {v!r}")
        return v


class Abastecimento(Base):
    __tablename__ = "abastecimento"
    __table_args__ = (
        UniqueConstraint("placa", "data", "km_hodometro", name="placa_data_km"), # rejeota dois abastecimentos com a msm placa na msm data
        Index("ix_abastecimento_placa_data", "placa", "data"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    placa: Mapped[str] = mapped_column(String(7), ForeignKey("veiculo.placa"), nullable=False, index=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    litros: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    valor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    km_hodometro: Mapped[Optional[int]] = mapped_column(Integer)          # ADR-002
    condutor_pseudo: Mapped[Optional[str]] = mapped_column(String)
    fonte_origem: Mapped[str] = mapped_column(String, nullable=False)


class Manutencao(Base):
    __tablename__ = "manutencao"
    __table_args__ = (
        CheckConstraint("tipo IN ('troca_oleo','filtros','pneus','revisao_geral')", name="tipo"),
        CheckConstraint("categoria IN ('preventiva','corretiva')", name="categoria"),
        UniqueConstraint("placa", "data", "tipo", name="placa_data_tipo"),
        Index("ix_manutencao_placa_tipo_data", "placa", "tipo", "data"),

    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    placa: Mapped[str] = mapped_column(String(7), ForeignKey("veiculo.placa"), nullable=False, index=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    categoria: Mapped[str] = mapped_column(String, nullable=False)        # ADR-003 item 7
    km_no_momento: Mapped[Optional[int]] = mapped_column(Integer)
    valor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    fonte_origem: Mapped[str] = mapped_column(String, nullable=False)


class Multa(Base):
    __tablename__ = "multa"
    __table_args__ = (
        CheckConstraint("situacao IN ('pendente','paga')", name="situacao"),
        UniqueConstraint("placa", "data", "valor", "condutor_pseudo", name="placa_data_valor_condutor"),
        Index("ix_multa_placa_data", "placa", "data"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    placa: Mapped[str] = mapped_column(String(7), ForeignKey("veiculo.placa"), nullable=False, index=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    condutor_pseudo: Mapped[Optional[str]] = mapped_column(String)
    situacao: Mapped[str] = mapped_column(String, nullable=False)
    fonte_origem: Mapped[str] = mapped_column(String, nullable=False)
    # SEM cnh/gravidade/codigo_infracao — minimização estrutural (ADR-003)


class Licenciamento(Base): # 1:1 com veiculo
    __tablename__ = "licenciamento"
    __table_args__ = (
        CheckConstraint("situacao IN ('em_dia','vencido')", name="situacao"),
        Index("ix_licenciamento_vencimento", "vencimento"), 
   )

    placa: Mapped[str] = mapped_column(String(7), ForeignKey("veiculo.placa"), primary_key=True)
    vencimento: Mapped[Optional[date]] = mapped_column(Date)
    situacao: Mapped[Optional[str]] = mapped_column(String)
    fonte_origem: Mapped[str] = mapped_column(String, nullable=False)



class LimiarConfig(Base):
    __tablename__ = "limiar_config"
    __table_args__ = (UniqueConstraint("tipo_veiculo", "tipo_manutencao", name="tipo_tipo"),)
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo_veiculo: Mapped[str] = mapped_column(String, nullable=False)
    tipo_manutencao: Mapped[str] = mapped_column(String, nullable=False)
    limite_km: Mapped[int] = mapped_column(Integer, nullable=False)
    limite_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    antecedencia_km: Mapped[int] = mapped_column(Integer, nullable=False)
    antecedencia_dias: Mapped[int] = mapped_column(Integer, nullable=False)
 

class Alerta(Base):
    __tablename__ = "alerta"
    __table_args__ = (
        CheckConstraint("tipo_gatilho IN ('km','tempo','dados_insuficientes')", name="tipo_gatilho"),
        CheckConstraint("situacao IN ('ativo','resolvido')", name="situacao"),
        Index("ix_alerta_situacao", "situacao"),
        
        # índice único parcial (research R6)
        # evitar colisao de alertas do mesmo tipo para o mesmo veiculo com dados insuficientes(NULL != NULL)
        Index(
            "ux_alerta_ativo",
            "placa", "tipo_gatilho", text("coalesce(limiar_id, -1)"),
            unique=True,
            sqlite_where=text("situacao = 'ativo'"),
            postgresql_where=text("situacao = 'ativo'"),
        ), 
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    placa: Mapped[str] = mapped_column(String(7), ForeignKey("veiculo.placa"), nullable=False, index=True)
    limiar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("limiar_config.id"))  # NULL p/ dados_insuficientes
    tipo_gatilho: Mapped[str] = mapped_column(String, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    situacao: Mapped[str] = mapped_column(String, nullable=False, default="ativo", server_default="ativo")
    detalhe: Mapped[Optional[str]] = mapped_column(String)  # "o que falta" (spec 004 FR-005)
 
 # ---------- Staging (tudo TEXT nullable; sem FK/CHECK/UNIQUE) ----------

class StgAbastecimento(Base):
    __tablename__ = "stg_abastecimento"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carga_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fonte_origem: Mapped[str] = mapped_column(Text, nullable=False)
    placa: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[Optional[str]] = mapped_column(Text)
    litros: Mapped[Optional[str]] = mapped_column(Text)
    valor: Mapped[Optional[str]] = mapped_column(Text)
    condutor: Mapped[Optional[str]] = mapped_column(Text)
    km: Mapped[Optional[str]] = mapped_column(Text)

class StgMultas(Base):       # carrega cnh sintética bruta (research R5)
    __tablename__ = "stg_multas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carga_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fonte_origem: Mapped[str] = mapped_column(Text, nullable=False)
    placa: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[Optional[str]] = mapped_column(Text)
    gravidade: Mapped[Optional[str]] = mapped_column(Text)
    valor: Mapped[Optional[str]] = mapped_column(Text)
    condutor: Mapped[Optional[str]] = mapped_column(Text)
    cnh: Mapped[Optional[str]] = mapped_column(Text)
    situacao: Mapped[Optional[str]] = mapped_column(Text)
    codigo_infracao: Mapped[Optional[str]] = mapped_column(Text)


class StgManutencao(Base):
    __tablename__ = "stg_manutencao"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carga_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fonte_origem: Mapped[str] = mapped_column(Text, nullable=False)
    placa: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[Optional[str]] = mapped_column(Text)
    tipo: Mapped[Optional[str]] = mapped_column(Text)
    categoria: Mapped[Optional[str]] = mapped_column(Text)
    km_no_momento: Mapped[Optional[str]] = mapped_column(Text)
    valor: Mapped[Optional[str]] = mapped_column(Text)
    aba_origem: Mapped[Optional[str]] = mapped_column(Text)


class StgLicenciamento(Base):
    __tablename__ = "stg_licenciamento"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carga_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fonte_origem: Mapped[str] = mapped_column(Text, nullable=False)
    placa: Mapped[Optional[str]] = mapped_column(Text)
    vencimento: Mapped[Optional[str]] = mapped_column(Text)
    situacao: Mapped[Optional[str]] = mapped_column(Text)

 #---------- Log de qualidade ----------

class LogQualidade(Base):
    __tablename__ = "log_qualidade"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fonte: Mapped[str] = mapped_column(String, nullable=False)
    registro_bruto: Mapped[str] = mapped_column(Text, nullable=False)
    motivo_rejeicao: Mapped[str] = mapped_column(String, nullable=False)
    carga_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)