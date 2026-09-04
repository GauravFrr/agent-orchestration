import json
import logging
from typing import Any, Dict

from app.agents.prompts.specialist_prompts import SPECIALIST_SYSTEM_PROMPT
from app.agents.supervisor import clean_json_text
from app.core.config import settings
from app.providers import get_default_provider
from app.tools.registry import invoke_tool

logger = logging.getLogger(__name__)

# Bounded tool set constant per coding style
ALLOWED_TOOLS = ["web_search", "file_read"]
SPECIALIST_NAME = "research"

class ResearchSpecialist:
    """
    Research Specialist Agent.
    Allowed tools: web_search, file_read
    """

    def __init__(self):
        self.provider = get_default_provider()

    async def execute(
        self,
        subtask_input: Dict[str, Any],
        expected_schema: Dict[str, Any],
        feedback_history: str = "",
        max_steps: int = 5,
        subtask_id: str = "",
        task_id: str = ""
    ) -> tuple[Dict[str, Any], int, int]:
        """
        Execute subtask using a ReAct loop with allowed tools.
        Enforces that web_search MUST be called before a final_answer is accepted.
        Returns:
            Tuple of (output_dict, input_tokens_count, output_tokens_count)
        """
        total_in_tokens = 0
        total_out_tokens = 0
        # Track whether the LLM has called at least one tool this execution
        tool_was_called = False
        # Max retries when LLM tries to skip tool use
        MAX_TOOL_RETRIES = 2
        tool_skip_retries = 0

        # Construct the context prompt for the specialist
        system_instruction = SPECIALIST_SYSTEM_PROMPT.format(
            specialist_name="Research",
            subtask_input=json.dumps(subtask_input, indent=2),
            feedback_history=feedback_history or "None"
        )

        # Guide the model on tool use formatting
        system_instruction += (
            f"\n\nYou have access to the following tools: {', '.join(ALLOWED_TOOLS)}.\n"
            "MANDATORY: You MUST call the 'web_search' tool at least once BEFORE providing any final_answer. "
            "If you respond with final_answer without first calling web_search, your response will be REJECTED.\n"
        )
        system_instruction += """To call a tool, output a JSON object matching this schema:
{
  "thought": "reasoning for calling the tool",
  "tool_call": {
    "name": "tool_name",
    "arguments": { ... }
  }
}

When you are ready to provide the final answer (only after calling web_search), output:
{
  "thought": "reasoning for final answer",
  "final_answer": { ... }
}
Make sure final_answer strictly conforms to this expected output schema:
""" + json.dumps(expected_schema, indent=2)

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Begin your task now. Your subtask input is:\n{json.dumps(subtask_input, indent=2)}"}
        ]

        model = settings.DEFAULT_MODEL_GEMINI if settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS else settings.DEFAULT_MODEL_CLAUDE

        from app.observability.cost import calculate_span_cost
        from app.observability.tracing import get_tracer
        tracer = get_tracer()

        for step in range(max_steps):
            logger.info(f"Research specialist step {step+1}/{max_steps}...")
            with tracer.start_as_current_span(
                "llm_call",
                attributes={
                    "task_id": str(task_id) if task_id else "",
                    "subtask_id": str(subtask_id) if subtask_id else "",
                    "span_type": "llm_call",
                    "actor": "specialist:research",
                    "model": model
                }
            ) as span:
                response, in_t, out_t = await self.provider.chat_completion(
                    model=model,
                    messages=messages
                )
                cost = calculate_span_cost(model, in_t, out_t)
                if span and hasattr(span, "set_attribute"):
                    span.set_attribute("tokens_in", in_t)
                    span.set_attribute("tokens_out", out_t)
                    span.set_attribute("cost_usd", cost)
                    span.set_attribute("payload", {"messages": messages, "response": response})

            total_in_tokens += in_t
            total_out_tokens += out_t

            try:
                cleaned_response = clean_json_text(response)
                parsed = json.loads(cleaned_response)

                # Check for tool call
                if "tool_call" in parsed and parsed["tool_call"]:
                    tool_name = parsed["tool_call"]["name"]
                    arguments = parsed["tool_call"].get("arguments", {})

                    if tool_name not in ALLOWED_TOOLS:
                        tool_result = f"Error: Tool '{tool_name}' is not in your allowed tool list: {ALLOWED_TOOLS}."
                    else:
                        logger.info(f"Research specialist invoking tool: {tool_name} with {arguments}")
                        tool_result_data = await invoke_tool(
                            tool_name,
                            SPECIALIST_NAME,
                            arguments,
                            subtask_id=subtask_id,
                            task_id=task_id
                        )
                        tool_result = json.dumps(tool_result_data)
                        tool_was_called = True

                    # Append response and tool result to messages
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": f"Tool '{tool_name}' returned: {tool_result}"
                    })

                # Check for final answer — only accept if tool was called first
                elif "final_answer" in parsed:
                    if not tool_was_called and tool_skip_retries < MAX_TOOL_RETRIES:
                        tool_skip_retries += 1
                        logger.warning(
                            f"Research specialist tried to skip web_search (retry {tool_skip_retries}/{MAX_TOOL_RETRIES}). "
                            "Forcing tool call."
                        )
                        messages.append({"role": "assistant", "content": response})
                        messages.append({
                            "role": "user",
                            "content": (
                                "REJECTED: You must call the 'web_search' tool before providing a final_answer. "
                                "This is a hard requirement. Call web_search now with a relevant query."
                            )
                        })
                    elif not tool_was_called:
                        logger.error("Research specialist failed to call web_search after max retries. Failing subtask.")
                        return {"error": "Research specialist did not call web_search as required."}, total_in_tokens, total_out_tokens
                    else:
                        logger.info("Research specialist completed successfully with final_answer.")
                        return parsed["final_answer"], total_in_tokens, total_out_tokens

                else:
                    logger.warning("Research specialist response didn't contain tool_call or final_answer.")
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": "Your response must contain either 'tool_call' or 'final_answer' in valid JSON format."
                    })

            except Exception as e:
                logger.error(f"Error parsing Research specialist output: {str(e)}. Raw: {response}")
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": f"Error parsing your JSON output: {str(e)}. Please output valid JSON matching the format instructions."
                })

        logger.warning(f"Research specialist reached max steps ({max_steps}) without returning final answer.")
        return {"error": "Max steps reached without output."}, total_in_tokens, total_out_tokens
