"""cache de respostas e uso diario do llm

Revision ID: c7a29f4e1b83
Revises: 11f738c7cae7
Create Date: 2026-08-05 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c7a29f4e1b83'
down_revision: Union[str, None] = '11f738c7cae7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('answer_cache',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('cache_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('answer', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('route', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('model_used', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_answer_cache_cache_key'), 'answer_cache', ['cache_key'], unique=False)
    op.create_table('llm_daily_usage',
    sa.Column('usage_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('call_count', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('usage_date')
    )


def downgrade() -> None:
    op.drop_table('llm_daily_usage')
    op.drop_index(op.f('ix_answer_cache_cache_key'), table_name='answer_cache')
    op.drop_table('answer_cache')
