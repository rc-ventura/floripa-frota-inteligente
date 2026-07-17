"""multa: chave de upsert por expressão (coalesce em condutor_pseudo)

Ciclo 1 da revisão SDD (ADR-004): a UNIQUE (placa, data, valor, condutor_pseudo)
não colidia quando condutor_pseudo era NULL (NULL≠NULL em SQL), quebrando a
promessa do contrato de que a 2ª multa idêntica vai para log_qualidade. Troca a
constraint por um índice único de expressão com coalesce('') — mesmo padrão do
ux_alerta_ativo. Abastecimento fica como está: NULL-km não colidir é decisão
documentada (research R7); dedup fina é do pipeline.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch: em SQLite, remover UNIQUE de CREATE TABLE exige rebuild da tabela
    with op.batch_alter_table('multa', schema=None) as batch_op:
        batch_op.drop_constraint('placa_data_valor_condutor', type_='unique')
    # expressão não é emitida pelo autogenerate em SQLite (mesmo caso do ux_alerta_ativo)
    op.create_index(
        'ux_multa_upsert',
        'multa',
        ['placa', 'data', 'valor', sa.text("coalesce(condutor_pseudo, '')")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ux_multa_upsert', table_name='multa')
    with op.batch_alter_table('multa', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'placa_data_valor_condutor', ['placa', 'data', 'valor', 'condutor_pseudo']
        )
