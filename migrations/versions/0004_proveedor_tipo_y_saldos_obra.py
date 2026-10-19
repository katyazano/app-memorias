"""agregar tipo y rfc nullable a proveedores, y 4 saldos iniciales a obras

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
import app.types

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Modificar tabla proveedores
    with op.batch_alter_table("proveedores", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "tipo",
                sa.Enum("con_factura", "sin_factura", name="tipo_proveedor", native_enum=False),
                server_default="con_factura",
                nullable=False,
            )
        )
        batch_op.alter_column(
            "rfc",
            existing_type=sa.String(length=13),
            nullable=True,
        )

    # 2. Modificar tabla obras (añadir 4 saldos iniciales)
    with op.batch_alter_table("obras", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("saldo_inicial_transferencias", app.types.DecimalText(), server_default="0.00", nullable=False)
        )
        batch_op.add_column(
            sa.Column("saldo_inicial_efectivo", app.types.DecimalText(), server_default="0.00", nullable=False)
        )
        batch_op.add_column(
            sa.Column("saldo_inicial_rayas", app.types.DecimalText(), server_default="0.00", nullable=False)
        )
        batch_op.add_column(
            sa.Column("saldo_inicial_memorias_anteriores", app.types.DecimalText(), server_default="0.00", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("obras", schema=None) as batch_op:
        batch_op.drop_column("saldo_inicial_memorias_anteriores")
        batch_op.drop_column("saldo_inicial_rayas")
        batch_op.drop_column("saldo_inicial_efectivo")
        batch_op.drop_column("saldo_inicial_transferencias")

    with op.batch_alter_table("proveedores", schema=None) as batch_op:
        batch_op.alter_column(
            "rfc",
            existing_type=sa.String(length=13),
            nullable=False,
        )
        batch_op.drop_column("tipo")
