import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine('postgresql+psycopg://postgres:postgres@db:5432/orchestration')
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE public.checkpoint_writes ADD COLUMN IF NOT EXISTS task_path TEXT NOT NULL DEFAULT ''"))
        await conn.execute(text("ALTER TABLE public.checkpoints ADD COLUMN IF NOT EXISTS type TEXT"))
    print("SCHEMA_ALTERED_SUCCESSFULLY")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
