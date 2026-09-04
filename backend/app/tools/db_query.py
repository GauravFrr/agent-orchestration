import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.tools.registry import register_tool

logger = logging.getLogger(__name__)

async def db_query(sql: str) -> dict:
    """
    Execute a read/write SQL query on the PostgreSQL database.
    This tool is scoped purely to the 'demo_data' schema using the Analyst user credentials.
    """
    logger.info(f"db_query tool called with query: '{sql}'")
    
    # Use ANALYST_DATABASE_URL to connect, enforcing postgres user permissions boundary
    engine = create_async_engine(settings.ANALYST_DATABASE_URL)
    
    try:
        async with engine.connect() as conn:
            # Enforce that the query searches only in demo_data schema by default
            await conn.execute(text("SET search_path TO demo_data;"))
            
            result = await conn.execute(text(sql))
            
            # Commit the transaction if write operation
            await conn.commit()
            
            # If the query returns rows (like SELECT), extract them
            if result.returns_rows:
                rows = result.fetchall()
                # Get column names
                columns = result.keys()
                # Format as list of dicts
                records = [dict(zip(columns, row)) for row in rows]
                return {
                    "success": True,
                    "row_count": len(records),
                    "columns": list(columns),
                    "results": records
                }
            else:
                return {
                    "success": True,
                    "row_count": result.rowcount,
                    "message": "Query executed successfully, no rows returned."
                }
                
    except Exception as e:
        logger.error(f"Database query error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        await engine.dispose()

# Auto-register this tool
register_tool(
    name="db_query",
    description="Execute an SQL query against the analysis demo_data database schema.",
    allowed_specialists=["data_analysis"],
    func=db_query,
    input_schema={
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "The raw SQL statement to execute. Only queries targeting demo_data tables are allowed."}
        },
        "required": ["sql"]
    }
)
