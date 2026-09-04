"""
Initial migration to set up the operational schema (tasks, subtasks, tool_invocations)
and the segmented demo_data schema.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'xxxx_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create public operational tables
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('request_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='intake'),
        sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_cost_usd', sa.Numeric(precision=10, scale=6), nullable=False, server_default='0.0'),
    )

    op.create_table(
        'subtasks',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('specialist', sa.String(), nullable=False),
        sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('depends_on', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reviewer_verdict', sa.String(), nullable=True),
        sa.Column('reviewer_feedback', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', 'task_id')
    )

    op.create_table(
        'tool_invocations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('subtask_id', sa.String(), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('tool_kind', sa.String(), nullable=False, server_default='custom'),
        sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(precision=10, scale=6), nullable=True, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['subtask_id', 'task_id'], ['subtasks.id', 'subtasks.task_id'], ondelete='CASCADE')
    )

    # 2. Create security segmented schema demo_data
    op.execute("CREATE SCHEMA IF NOT EXISTS demo_data;")

    # 3. Create demo_data sample tables
    op.execute("""
        CREATE TABLE IF NOT EXISTS demo_data.sales_data (
            id SERIAL PRIMARY KEY,
            product_name VARCHAR(100) NOT NULL,
            units_sold INTEGER NOT NULL,
            sale_amount NUMERIC(10, 2) NOT NULL,
            sale_date DATE NOT NULL
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS demo_data.inventory (
            id SERIAL PRIMARY KEY,
            product_name VARCHAR(100) NOT NULL,
            stock_level INTEGER NOT NULL,
            supplier_name VARCHAR(100) NOT NULL
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS demo_data.employees (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            department VARCHAR(100) NOT NULL,
            salary NUMERIC(10, 2) NOT NULL,
            hire_date DATE NOT NULL
        );
    """)

def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS demo_data CASCADE;")
    op.drop_table('tool_invocations')
    op.drop_table('subtasks')
    op.drop_table('tasks')
