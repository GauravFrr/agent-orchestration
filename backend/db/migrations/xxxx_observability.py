"""
Create trace_spans and replays tables.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'xxxx_observability'
down_revision = 'xxxx_hitl'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create trace_spans table
    op.create_table(
        'trace_spans',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parent_span_id', sa.String(), nullable=True),
        sa.Column('span_type', sa.String(), nullable=False),
        sa.Column('actor', sa.String(), nullable=False),
        sa.Column('subtask_id', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True, server_default='0.0'),
        sa.Column('tokens_in', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('tokens_out', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE')
    )
    op.create_index('idx_trace_spans_task_id', 'trace_spans', ['task_id'])

    # Create replays table
    op.create_table(
        'replays',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('original_task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_checkpoint_id', sa.String(), nullable=False),
        sa.Column('input_override', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resulting_task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['original_task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resulting_task_id'], ['tasks.id'], ondelete='CASCADE')
    )

def downgrade() -> None:
    op.drop_table('replays')
    op.drop_index('idx_trace_spans_task_id', table_name='trace_spans')
    op.drop_table('trace_spans')
