import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import memory, reviews, tasks, traces
from db.models import Base, engine

# Setup logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Agent Orchestration System API",
    description="Decomposes, executes, and validates natural language tasks using specialized agents.",
    version="1.0.0"
)

# CORS middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount Routers
app.include_router(tasks.router)
app.include_router(memory.router)
app.include_router(reviews.router)
app.include_router(traces.router)

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing operational database tables...")
    try:
        async with engine.begin() as conn:
            # Create all tables in public operational schema
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Successfully created database tables on startup.")
    except Exception as e:
        logger.error(f"Error creating database tables on startup: {str(e)}")

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "agent-orchestration-backend"}
