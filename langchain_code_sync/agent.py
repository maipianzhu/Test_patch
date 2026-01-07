from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_code_sync.utils.state import AgentState
from langchain_code_sync.utils.nodes import (
    generate_patches,
    apply_next_patch,
    analyze_conflict,
    process_user_decision,
)


def route_after_apply(
    state: AgentState,
) -> Literal["apply_next_patch", "analyze_conflict", "end"]:
    if state.get("conflict_error"):
        return "analyze_conflict"

    if state["current_patch_index"] < len(state["patches"]):
        return "apply_next_patch"

    return "end"


def route_after_resolve(state: AgentState) -> Literal["apply_next_patch", "end"]:
    # If user chose abort, patches might be cleared or we need a flag.
    # Based on node logic:
    if state["current_patch_index"] < len(state["patches"]):
        return "apply_next_patch"
    return "end"


workflow = StateGraph(AgentState)

workflow.add_node("generate_patches", generate_patches)
workflow.add_node("apply_next_patch", apply_next_patch)
workflow.add_node("analyze_conflict", analyze_conflict)
workflow.add_node("process_user_decision", process_user_decision)

workflow.set_entry_point("generate_patches")

workflow.add_edge("generate_patches", "apply_next_patch")

workflow.add_conditional_edges(
    "apply_next_patch",
    route_after_apply,
    {
        "apply_next_patch": "apply_next_patch",
        "analyze_conflict": "analyze_conflict",
        "end": END,
    },
)

# Human in the loop: Interrupt before process_user_decision?
# Actually, we want to show suggestion -> Interrupt -> Get Input -> Process
# LangGraph `interrupt` is usually implicit if we use a breakpoint or an input node.
# But for now, we can structure it such that we'll assume `analyze_conflict` sets the suggestion
# and then we effectively pause. In a real executed graph we might set a breakpoint.
# Here we wire it to `process_user_decision` but we'll assume the runtime (if we were running it)
# would pause before `process_user_decision`.

workflow.add_edge("analyze_conflict", "process_user_decision")

workflow.add_conditional_edges(
    "process_user_decision",
    route_after_resolve,
    {"apply_next_patch": "apply_next_patch", "end": END},
)

# compiled_graph = workflow.compile(interrupt_before=["process_user_decision"])
# For now just compile without explicit interrupts as we are building the code,
# the runner would handle the interrupt configuration.
app = workflow.compile()
