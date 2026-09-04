import asyncio
import logging
from app.graph.checkpointing import get_checkpointer

logging.basicConfig(level=logging.INFO)

async def main():
    checkpointer = get_checkpointer()
    await checkpointer.conn.open()
    await checkpointer.setup()
    print("CHECKPOINTER_SETUP_SUCCESSFUL")

if __name__ == "__main__":
    asyncio.run(main())
