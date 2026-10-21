"""agregar tabla registros_auditoria

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20 03:40:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registros_auditoria",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fecha", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("accion", sa.String(length=100), nullable=False),
        sa.Column("memoria_id", sa.Integer(), nullable=True),
        sa.Column("obra_id", sa.Integer(), nullable=True),
        sa.Column("detalles", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["memoria_id"], ["memorias.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["obra_id"], ["obras.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_registros_auditoria_accion"), "registros_auditoria", ["accion"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_registros_auditoria_accion"), table_name="registros_auditoria")
    op.drop_table("registros_auditoria")
