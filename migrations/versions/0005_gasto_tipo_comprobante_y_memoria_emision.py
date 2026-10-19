"""agregar tipo_comprobante a gastos y fecha_emision/ciudad a memorias

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-16 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Modificar tabla gastos (añadir tipo_comprobante)
    with op.batch_alter_table("gastos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("tipo_comprobante", sa.String(length=20), server_default="NOTA", nullable=False)
        )

    # Actualizar gastos de XML para que tengan tipo_comprobante = 'FACTURA'
    op.execute("UPDATE gastos SET tipo_comprobante = 'FACTURA' WHERE origen = 'xml'")

    # 2. Modificar tabla memorias (añadir fecha_emision y ciudad)
    with op.batch_alter_table("memorias", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("fecha_emision", sa.Date(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ciudad", sa.String(length=100), server_default="Zapopan, Jalisco", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("memorias", schema=None) as batch_op:
        batch_op.drop_column("ciudad")
        batch_op.drop_column("fecha_emision")

    with op.batch_alter_table("gastos", schema=None) as batch_op:
        batch_op.drop_column("tipo_comprobante")
