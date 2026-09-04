"""
Create review_requests, checkpoints, and hitl_configs tables, and add action_tag column to subtasks.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'xxxx_hitl'
down_revision = 'xxxx_memory'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add action_tag column to subtasks table
    op.add_column('subtasks', sa.Column('action_tag', sa.String(), nullable=True))

    # Create review_requests table
    op.create_table(
        'review_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subtask_id', sa.String(), nullable=True),
        sa.Column('trigger_reason', sa.String(), nullable=False),
        sa.Column('approval_level', sa.String(), nullable=False),
        sa.Column('context_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('decision_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE')
    )

    # Create checkpoints table
    op.create_table(
        'checkpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_name', sa.String(), nullable=False),
        sa.Column('state_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE')
    )

    # Create hitl_configs table
    op.create_table(
        'hitl_configs',
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('description', sa.Text(), nullable=True)
    )

    # Create partial unique index to enforce single pending review request per task + subtask at DB level
    op.create_index(
        'uq_pending_review',
        'review_requests',
        ['task_id', 'subtask_id'],
        unique=True,
        postgresql_where=sa.text("status = 'pending'")
    )

def downgrade() -> None:
    op.drop_index('uq_pending_review', table_name='review_requests')
    op.drop_table('hitl_configs')
    op.drop_table('checkpoints')
    op.drop_table('review_requests')
    op.drop_column('subtasks', 'action_tag')
