import logging

from langgraph.graph import END, StateGraph

from app.graph.nodes.dispatch import dispatch_node
from app.graph.nodes.intake import intake_node
from app.graph.nodes.plan import plan_node
from app.graph.nodes.review import review_node
from app.graph.nodes.synthesize import synthesize_node
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

def should_continue(state: AgentState) -> str:
    """
    Conditional routing edge. Determines if the graph should run more subtasks or synthesize results.
    """
    plan = state.get("plan")
    results = state.get("results", {})
    status = state.get("status")

    if status == "escalated":
        logger.info("Graph state status is 'escalated'. Ending workflow execution.")
        return END

    if not plan or not plan.subtasks:
        logger.warning("No plan or subtasks found in state. Synthesizing.")
        return "synthesize"

    # Check if all subtasks in the plan have results
    all_done = True
    for subtask in plan.subtasks:
        if subtask.id not in results:
            all_done = False
            break

    if all_done:
        logger.info("All plan subtasks completed. Routing to synthesis node.")
        return "synthesize"

    # Check if we hit a failure state (e.g. error keys in results or empty ready subtasks)
    # Check if any ready subtasks exist
    ready_subtasks = []
    for subtask in plan.subtasks:
        if subtask.id in results:
            continue
        all_deps_met = True
        for dep_id in subtask.depends_on:
            if dep_id not in results:
                all_deps_met = False
                break
        if all_deps_met:
            ready_subtasks.append(subtask)

    if not ready_subtasks:
        logger.warning("No ready subtasks can be run (possibly circular dependencies or error blocks). Routing to synthesis.")
        return "synthesize"

    logger.info("Plan execution in progress. Routing to review node.")
    return "review"

def build_workflow():
    """
    Wiring the nodes and conditional edges of the LangGraph state machine.
    """
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("dispatch", dispatch_node)
    workflow.add_node("review", review_node)
    workflow.add_node("synthesize", synthesize_node)

    # Set entry point
    workflow.set_entry_point("intake")

    # Add simple linear edges
    workflow.add_edge("intake", "plan")
    workflow.add_edge("plan", "dispatch")
    # Add conditional edge from dispatch node (to handle HITL escalation pause)
    workflow.add_conditional_edges(
        "dispatch",
        should_continue,
        {
            "review": "review",
            "synthesize": "synthesize",
            END: END
        }
    )

    # Add conditional edge from review node
    workflow.add_conditional_edges(
        "review",
        should_continue,
        {
            "dispatch": "dispatch",
            "synthesize": "synthesize",
            END: END
        }
    )

    # Synthesis is the final node
    workflow.add_edge("synthesize", END)

    # Compile the graph with native AsyncPostgresSaver checkpointer
    from app.graph.checkpointing import get_checkpointer
    checkpointer = get_checkpointer()
    app_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("Successfully compiled LangGraph workflow with native AsyncPostgresSaver checkpointer.")
    return app_graph
