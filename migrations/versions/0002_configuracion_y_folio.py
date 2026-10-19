"""configuracion y folio_factura_arquitecto

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-09 12:05:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "configuraciones",
        sa.Column("clave", sa.String(length=100), primary_key=True, nullable=False),
        sa.Column("valor", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
    )
    with op.batch_alter_table("memorias", schema=None) as batch_op:
        batch_op.add_column(sa.Column("folio_factura_arquitecto", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("memorias", schema=None) as batch_op:
        batch_op.drop_column("folio_factura_arquitecto")
    op.drop_table("configuraciones")
