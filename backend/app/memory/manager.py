import json
import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.agents.supervisor import clean_json_text
from app.core.config import settings
from app.memory.long_term import add_to_collection, get_embedding, query_collection
from app.providers import get_default_provider
from db.models import AsyncSessionLocal, Memory, Subtask, Task

logger = logging.getLogger(__name__)

class MemoryExtraction(BaseModel):
    plan_summary: str = Field(description="A short, one-sentence summary of the task plan and its outcome")
    facts: list[str] = Field(default_factory=list, description="Key factual details or findings discovered during execution")
    preferences: list[str] = Field(default_factory=list, description="User preferences or constraints inferred from the interaction")

class MemoryManager:
    """
    Orchestrates the short and long-term memory systems.
    Retrieves context for planning and creates memories post-completion.
    """

    async def retrieve_context(self, request_text: str, k: int = 2) -> str:
        """
        Query ChromaDB collections for similar past plans, facts, and preferences.
        Updates retrieval counts and importance scores in PostgreSQL.
        Returns a formatted markdown text block containing the retrieved context.
        """
        try:
            logger.info(f"Retrieving memory context for: '{request_text}'")
            query_emb = await get_embedding(request_text)

            # Query all 3 collections in parallel
            plans_res = await query_collection("plans", query_emb, n_results=k)
            facts_res = await query_collection("facts", query_emb, n_results=k)
            prefs_res = await query_collection("preferences", query_emb, n_results=k)

            retrieved_ids = []
            context_parts = []

            # 1. Process Plan Matches
            if plans_res and plans_res.get("documents") and plans_res["documents"][0]:
                context_parts.append("### Similar Past Plans")
                for doc, metadata, doc_id in zip(plans_res["documents"][0], plans_res["metadatas"][0], plans_res["ids"][0]):
                    retrieved_ids.append(doc_id)
                    outcome = metadata.get("outcome", "unknown")
                    summary = metadata.get("final_plan_summary", "")
                    context_parts.append(
                        f"- **Request**: \"{doc}\"\n"
                        f"  **Outcome**: {outcome}\n"
                        f"  **Plan Summary**: {summary}"
                    )

            # 2. Process Fact Matches
            if facts_res and facts_res.get("documents") and facts_res["documents"][0]:
                context_parts.append("\n### Related Domain Facts")
                for doc, metadata, doc_id in zip(facts_res["documents"][0], facts_res["metadatas"][0], facts_res["ids"][0]):
                    retrieved_ids.append(doc_id)
                    specialist = metadata.get("specialist", "unknown")
                    context_parts.append(f"- \"{doc}\" (Discovered by: {specialist} specialist)")

            # 3. Process Preference Matches
            if prefs_res and prefs_res.get("documents") and prefs_res["documents"][0]:
                context_parts.append("\n### User Preferences")
                for doc, metadata, doc_id in zip(prefs_res["documents"][0], prefs_res["metadatas"][0], prefs_res["ids"][0]):
                    retrieved_ids.append(doc_id)
                    context_parts.append(f"- Preferred: {doc}")

            # Update retrieval metadata in Postgres
            if retrieved_ids:
                await self._update_retrieval_stats(retrieved_ids)

            if context_parts:
                return "\n=== RETRIEVED CONTEXT FROM PAST EXECUTIONS ===\n" + "\n".join(context_parts) + "\n=============================================\n"
        except Exception as e:
            logger.error(f"Error in retrieve_context: {str(e)}")

        return ""

    async def _update_retrieval_stats(self, doc_ids: List[str]):
        """
        Increment retrieval count and update importance score for matching Postgres rows.
        """
        try:
            async with AsyncSessionLocal() as session:
                for doc_id in doc_ids:
                    try:
                        uuid_id = UUID(doc_id)
                        mem = await session.get(Memory, uuid_id)
                        if mem:
                            mem.retrieval_count += 1
                            mem.last_retrieved_at = datetime.utcnow()
                            # Recalculate score: outcome factor + 0.1 * retrieval_count
                            outcome_factor = 1.0 if mem.importance_score >= 0.5 else 0.2
                            mem.importance_score = min(2.5, outcome_factor + (0.1 * mem.retrieval_count))
                    except ValueError:
                        continue
                await session.commit()
        except Exception as e:
            logger.error(f"Error updating memory stats: {str(e)}")

    async def create_memories(self, task_id: str, request_text: str, plan: Dict[str, Any], status: str):
        """
        Analyze completed task execution to extract plans, facts, and user preferences.
        Saves memories to Postgres table and ChromaDB collections.
        """
        try:
            logger.info(f"Extracting memories for completed task {task_id} with status {status}...")

            # Fetch subtask details to get outputs for extraction
            subtasks_data = []
            async with AsyncSessionLocal() as session:
                task_uuid = UUID(task_id)
                query = select(Subtask).where(Subtask.task_id == task_uuid)
                res = await session.execute(query)
                subtasks = res.scalars().all()
                for st in subtasks:
                    subtasks_data.append({
                        "specialist": st.specialist,
                        "input": st.input,
                        "output": st.output,
                        "feedback": st.reviewer_feedback
                    })

            # Call Gemini to extract facts & preferences
            extracted = await self._extract_memories_via_llm(request_text, plan, subtasks_data)

            # Insert memories
            async with AsyncSessionLocal() as session:
                task_uuid = UUID(task_id)
                base_score = 1.0 if status == "done" else 0.5

                # 1. Save Plan Memory
                plan_uuid = uuid4()
                plan_mem = Memory(
                    id=plan_uuid,
                    source_task_id=task_uuid,
                    memory_type="plan",
                    summary=extracted.plan_summary,
                    importance_score=base_score,
                    created_at=datetime.utcnow()
                )
                session.add(plan_mem)
                # Save to Chroma
                plan_emb = await get_embedding(request_text)
                await add_to_collection(
                    "plans",
                    str(plan_uuid),
                    request_text,
                    plan_emb,
                    {"task_id": task_id, "final_plan_summary": extracted.plan_summary, "outcome": status}
                )

                # 2. Save Fact Memories
                for fact in extracted.facts:
                    fact_uuid = uuid4()
                    fact_mem = Memory(
                        id=fact_uuid,
                        source_task_id=task_uuid,
                        memory_type="fact",
                        summary=fact,
                        importance_score=base_score,
                        created_at=datetime.utcnow()
                    )
                    session.add(fact_mem)

                    fact_emb = await get_embedding(fact)
                    await add_to_collection(
                        "facts",
                        str(fact_uuid),
                        fact,
                        fact_emb,
                        {"task_id": task_id, "fact_text": fact, "specialist": "extracted"}
                    )

                # 3. Save Preference Memories
                for pref in extracted.preferences:
                    pref_uuid = uuid4()
                    pref_mem = Memory(
                        id=pref_uuid,
                        source_task_id=task_uuid,
                        memory_type="preference",
                        summary=pref,
                        importance_score=base_score,
                        created_at=datetime.utcnow()
                    )
                    session.add(pref_mem)

                    pref_emb = await get_embedding(pref)
                    await add_to_collection(
                        "preferences",
                        str(pref_uuid),
                        pref,
                        pref_emb,
                        {"task_id": task_id, "preference_text": pref}
                    )

                await session.commit()
                logger.info(f"Successfully saved all long-term memories for task {task_id}")
        except Exception as e:
            logger.error(f"Error in create_memories: {str(e)}")

    async def _extract_memories_via_llm(self, request_text: str, plan: Dict[str, Any], subtasks: List[Dict[str, Any]]) -> MemoryExtraction:
        """
        Use Gemini structured output mode to extract facts and preferences from task execution context.
        """
        if settings.MOCK_PROVIDERS or not settings.GEMINI_API_KEY:
            # Deterministic mock memory extraction based on request keywords
            plan_summary = f"Executed {len(plan.get('subtasks', []))} subtasks for request: '{request_text}'"
            facts = []
            if "LangGraph" in request_text or "langgraph" in request_text.lower():
                facts.append("The latest LangGraph release is v0.2.60, introducing functional entrypoints (@task, @entrypoint) and enhanced state persistence.")
            else:
                facts.append("Discovered standard operational trends and data matching the user's orchestration request.")
            return MemoryExtraction(
                plan_summary=plan_summary,
                facts=facts,
                preferences=["Prefers summarized structured details for technical queries."]
            )

        provider = get_default_provider()
        model = settings.DEFAULT_MODEL_GEMINI

        system_instruction = (
            "You are a Memory Extraction Assistant. Analyze the completed task request, plan, and specialist subtask execution outputs. "
            "Extract:\n"
            "1. A concise, one-sentence plan_summary of how the request was executed and what was accomplished.\n"
            "2. Specific, clear domain facts discovered during execution (e.g. software versions, statistics, database facts).\n"
            "3. Any inferred user preferences or formatting constraints (e.g. 'prefers tables', 'excludes draft text').\n"
            "Output must strictly follow the response schema."
        )

        user_content = {
            "request_text": request_text,
            "plan": plan,
            "subtasks_execution": subtasks
        }

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": json.dumps(user_content, indent=2)}
        ]

        try:
            # Call Gemini provider
            response, _, _ = await provider.chat_completion(
                model=model,
                messages=messages,
                response_schema=MemoryExtraction
            )
            cleaned = clean_json_text(response)
            parsed = json.loads(cleaned)
            return MemoryExtraction(**parsed)
        except Exception as e:
            logger.error(f"Error calling LLM for memory extraction: {str(e)}")
            # Return simple fallback
            return MemoryExtraction(
                plan_summary=f"Processed plan for request: '{request_text}'",
                facts=["Executed task workflow without critical errors."],
                preferences=[]
            )
