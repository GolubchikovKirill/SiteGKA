"""add connection_type and host_pc to printer

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-23 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('printer', sa.Column('connection_type', sa.String(length=10), nullable=False, server_default='ip'))
    op.add_column('printer', sa.Column('host_pc', sa.String(length=255), nullable=True))
    op.alter_column('printer', 'ip_address', existing_type=sa.String(length=45), nullable=True)
    op.drop_constraint('printer_ip_address_key', 'printer', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('printer_ip_address_key', 'printer', ['ip_address'])
    op.alter_column('printer', 'ip_address', existing_type=sa.String(length=45), nullable=False)
    op.drop_column('printer', 'host_pc')
    op.drop_column('printer', 'connection_type')
