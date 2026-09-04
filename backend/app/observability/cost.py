import logging

from app.core.cost import PRICING, calculate_cost, record_llm_cost

logger = logging.getLogger(__name__)

def calculate_span_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Consolidated helper to compute USD token cost for a given model and token counts.
    Reuses the authoritative pricing table defined in app.core.cost.
    """
    return calculate_cost(model, input_tokens, output_tokens)

__all__ = ["PRICING", "calculate_cost", "record_llm_cost", "calculate_span_cost"]
