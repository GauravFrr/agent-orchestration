import asyncio
import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from db.models import Base

logger = logging.getLogger(__name__)

async def get_admin_engine():
    db_host = os.environ.get("DB_HOST", "localhost")
    candidates = []
    if os.environ.get("POSTGRES_ADMIN_URL"):
        candidates.append(os.environ["POSTGRES_ADMIN_URL"])
    candidates.append(f"postgresql+psycopg://postgres:postgres@{db_host}:5432/orchestration")
    if os.environ.get("DATABASE_URL"):
        candidates.append(os.environ["DATABASE_URL"])

    tested = set()
    for url in candidates:
        if url in tested:
            continue
        tested.add(url)
        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info(f"Connected to database admin using: {url.split('@')[-1]}")
            return engine
        except Exception as e:
            logger.warning(f"Could not connect using {url.split('@')[-1]}: {e}")
            continue

    raise RuntimeError("Failed to connect to database with any admin URL candidate.")

async def initialize_database():
    """
    Initialize the database schemas, roles, tables, and mock data.
    """
    engine = await get_admin_engine()

    logger.info("Starting database initialization...")

    async with engine.begin() as conn:
        # 0. Ensure base operational tables exist
        logger.info("Creating base operational tables from metadata...")
        await conn.run_sync(Base.metadata.create_all)

        # 1. Create Roles/Users (if superuser and roles don't exist)
        logger.info("Creating roles orchestrator and analyst if missing...")
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper = true) THEN
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'orchestrator') THEN
                        CREATE ROLE orchestrator WITH LOGIN PASSWORD 'orchestrator_pass';
                    END IF;
                    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'analyst') THEN
                        CREATE ROLE analyst WITH LOGIN PASSWORD 'analyst_pass';
                    END IF;
                END IF;
            END
            $$;
        """))

        # 2. Create demo_data schema
        logger.info("Creating demo_data schema...")
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS demo_data;"))

        # 3. Create sample tables inside demo_data schema
        logger.info("Creating sample tables in demo_data...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS demo_data.sales_data (
                id SERIAL PRIMARY KEY,
                product_name VARCHAR(100) NOT NULL,
                units_sold INTEGER NOT NULL,
                sale_amount NUMERIC(10, 2) NOT NULL,
                sale_date DATE NOT NULL
            );
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS demo_data.inventory (
                id SERIAL PRIMARY KEY,
                product_name VARCHAR(100) NOT NULL,
                stock_level INTEGER NOT NULL,
                supplier_name VARCHAR(100) NOT NULL
            );
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS demo_data.employees (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                salary NUMERIC(10, 2) NOT NULL,
                hire_date DATE NOT NULL
            );
        """))

        # 4. Seed mock data into sample tables
        logger.info("Seeding mock data into demo_data tables...")

        # Clear existing rows to prevent duplicate primary key errors during repeated seeds
        await conn.execute(text("TRUNCATE TABLE demo_data.sales_data RESTART IDENTITY CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE demo_data.inventory RESTART IDENTITY CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE demo_data.employees RESTART IDENTITY CASCADE;"))

        await conn.execute(text("""
            INSERT INTO demo_data.sales_data (product_name, units_sold, sale_amount, sale_date) VALUES
            ('AI Chipset Alpha', 120, 144000.00, '2026-08-01'),
            ('Neural Coprocessor V2', 80, 96000.00, '2026-08-10'),
            ('Quantum Qubit Module', 5, 250000.00, '2026-08-15'),
            ('AI Chipset Alpha', 150, 180000.00, '2026-08-20');
        """))

        await conn.execute(text("""
            INSERT INTO demo_data.inventory (product_name, stock_level, supplier_name) VALUES
            ('AI Chipset Alpha', 450, 'Silicon Dynamics Corp'),
            ('Neural Coprocessor V2', 120, 'NextGen Processors Ltd'),
            ('Quantum Qubit Module', 3, 'Quantum Labs Inc');
        """))

        await conn.execute(text("""
            INSERT INTO demo_data.employees (name, department, salary, hire_date) VALUES
            ('Alice Smith', 'Engineering', 125000.00, '2022-03-15'),
            ('Bob Jones', 'Data Science', 135000.00, '2023-06-01'),
            ('Charlie Brown', 'Operations', 95000.00, '2024-01-10');
        """))

        # 5. Grant Permissions (Segmentation Boundary) safely
        logger.info("Configuring database segmentation grants...")
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'orchestrator') THEN
                    GRANT ALL PRIVILEGES ON SCHEMA public TO orchestrator;
                    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO orchestrator;
                    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO orchestrator;
                END IF;

                IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'analyst') THEN
                    REVOKE ALL PRIVILEGES ON SCHEMA public FROM analyst;
                    GRANT ALL PRIVILEGES ON SCHEMA demo_data TO analyst;
                    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA demo_data TO analyst;
                    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA demo_data TO analyst;
                    ALTER DEFAULT PRIVILEGES IN SCHEMA demo_data GRANT ALL PRIVILEGES ON TABLES TO analyst;
                END IF;
            END
            $$;
        """))

        # 6. Schema Migrations & HITL Configurations
        logger.info("Applying additive schema migrations and seeding HITL configurations...")
        await conn.execute(text("ALTER TABLE public.subtasks ADD COLUMN IF NOT EXISTS action_tag VARCHAR;"))

        # Seed HITL configs if hitl_configs table exists
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.hitl_configs (
                key VARCHAR PRIMARY KEY,
                value JSONB NOT NULL,
                description TEXT
            );
        """))

        await conn.execute(text("""
            INSERT INTO public.hitl_configs (key, value, description) VALUES
            ('low_confidence_threshold', '{"val": 0.8}'::jsonb, 'Threshold below which plan triggers review'),
            ('max_subtask_failures', '{"val": 2}'::jsonb, 'Max retries before repeated_failure escalation'),
            ('sensitive_action_tags', '["financial", "deletion", "external_communication"]'::jsonb, 'Sensitive tags requiring approval'),
            ('trigger_to_level_mapping', '{"low_confidence": "approve_plan", "sensitive_action": "approve_action", "repeated_failure": "take_over", "reviewer_flag": "notify"}'::jsonb, 'Trigger to approval level mapping')
            ON CONFLICT (key) DO NOTHING;
        """))

        # DB-level partial unique index hard guarantee
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_review ON public.review_requests (task_id, subtask_id) WHERE status = 'pending';"))

        # Create trace_spans and replays tables if not existing
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.trace_spans (
                id VARCHAR PRIMARY KEY,
                task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
                parent_span_id VARCHAR,
                span_type VARCHAR NOT NULL,
                actor VARCHAR NOT NULL,
                subtask_id VARCHAR,
                started_at TIMESTAMPTZ NOT NULL,
                ended_at TIMESTAMPTZ NOT NULL,
                latency_ms INT NOT NULL DEFAULT 0,
                cost_usd NUMERIC(10, 6) DEFAULT 0.0,
                tokens_in INT DEFAULT 0,
                tokens_out INT DEFAULT 0,
                payload JSONB NOT NULL DEFAULT '{}'::jsonb
            );
            CREATE INDEX IF NOT EXISTS idx_trace_spans_task_id ON public.trace_spans (task_id);

            CREATE TABLE IF NOT EXISTS public.replays (
                id UUID PRIMARY KEY,
                original_task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
                from_checkpoint_id VARCHAR NOT NULL,
                input_override JSONB,
                resulting_task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS public.checkpoint_migrations (v INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS public.checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint JSONB NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}',
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
            CREATE TABLE IF NOT EXISTS public.checkpoint_blobs (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                channel TEXT NOT NULL,
                version TEXT NOT NULL,
                type TEXT NOT NULL,
                blob BYTEA,
                PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
            );
            CREATE TABLE IF NOT EXISTS public.checkpoint_writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT,
                blob BYTEA NOT NULL,
                task_path TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            );
            CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON public.checkpoints(thread_id);
            CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON public.checkpoint_blobs(thread_id);
            CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON public.checkpoint_writes(thread_id);
            INSERT INTO public.checkpoint_migrations (v) VALUES (1), (2), (3), (4), (5), (6), (7), (8), (9), (10) ON CONFLICT (v) DO NOTHING;
        """))

        logger.info("Database security segmentation, HITL schema, Observability tables, and LangGraph Postgres checkpointer tables successfully configured.")

    await engine.dispose()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(initialize_database())

