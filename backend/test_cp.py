import asyncio
import logging
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test():
    conn_str = settings.DATABASE_URL
    logger.info(f"Connecting AsyncPostgresSaver to {conn_str}...")
    async with AsyncPostgresSaver.from_conn_string(conn_str) as checkpointer:
        await checkpointer.setup()
        logger.info(f"AsyncPostgresSaver initialized and setup successfully! Checkpointer: {checkpointer}")

if __name__ == "__main__":
    asyncio.run(test())
