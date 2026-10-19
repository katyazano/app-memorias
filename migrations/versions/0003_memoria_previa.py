"""agregar numero_ultima_memoria_previa a obras

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09 13:45:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("obras", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("numero_ultima_memoria_previa", sa.Integer(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("obras", schema=None) as batch_op:
        batch_op.drop_column("numero_ultima_memoria_previa")
