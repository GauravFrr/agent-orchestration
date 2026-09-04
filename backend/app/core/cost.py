import logging
from uuid import UUID

from sqlalchemy import update

from db.models import AsyncSessionLocal, Task

logger = logging.getLogger(__name__)

# Prices per token (USD)
PRICING = {
    # Gemini 3.x Models
    "gemini-3.7-flash": {
        "input": 0.075 / 1_000_000,
        "output": 0.30 / 1_000_000
    },
    "gemini-3.6-flash": {
        "input": 0.075 / 1_000_000,
        "output": 0.30 / 1_000_000
    },
    "gemini-3.5-flash": {
        "input": 0.075 / 1_000_000,
        "output": 0.30 / 1_000_000
    },
    "gemini-2.5-flash": {
        "input": 0.075 / 1_000_000,
        "output": 0.30 / 1_000_000
    },
    "gemini-1.5-flash": {
        "input": 0.075 / 1_000_000,
        "output": 0.30 / 1_000_000
    },
    # Claude 3.5 Sonnet
    "claude-3-5-sonnet-latest": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000
    },
    # Groq (Llama 3.3 70b)
    "llama-3.3-70b-versatile": {
        "input": 0.59 / 1_000_000,
        "output": 0.79 / 1_000_000
    }
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate USD cost based on token counts.
    """
    # Normalize model names
    model_lower = model.lower()
    rates = None
    for name, rate_dict in PRICING.items():
        if name in model_lower:
            rates = rate_dict
            break

    # Default fallback to Gemini 3.6 Flash rates if unknown
    if not rates:
        rates = PRICING["gemini-3.6-flash"]

    cost = (input_tokens * rates["input"]) + (output_tokens * rates["output"])
    return round(cost, 6)

async def record_llm_cost(task_id: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate and accumulate LLM call cost into the task's total_cost_usd.
    """
    if not task_id:
        return 0.0

    cost = calculate_cost(model, input_tokens, output_tokens)
    if cost <= 0.0:
        return 0.0

    logger.info(f"LLM call on model {model} cost ${cost:.6f} ({input_tokens} in, {output_tokens} out)")

    try:
        async with AsyncSessionLocal() as session:
            task_uuid = UUID(task_id)
            # Accumulate cost inside DB row
            await session.execute(
                update(Task)
                .where(Task.id == task_uuid)
                .values(total_cost_usd=Task.total_cost_usd + cost)
            )
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to record LLM cost in database: {str(e)}")

    return cost
