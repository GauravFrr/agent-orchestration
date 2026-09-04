"""
Create memories table
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'xxxx_memory'
down_revision = 'xxxx_initial'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('memory_type', sa.String(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('importance_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('retrieval_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retrieved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_task_id'], ['tasks.id'], ondelete='CASCADE')
    )

def downgrade() -> None:
    op.drop_table('memories')
