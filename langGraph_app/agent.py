from langgraph.graph import StateGraph, START, END

from langGraph_app.utils.state import AgentState
from langGraph_app.utils.nodes import (
    agent_node,
    tool_node,
    human_review_node,
    route_tools,
    check_approval,
    rejection_node,
)

# 1. Initialize Graph
workflow = StateGraph(AgentState)

# 2. Add Nodes
workflow.add_node("agent", agent_node)
workflow.add_node("human_review_node", human_review_node)
workflow.add_node("rejection_node", rejection_node)
workflow.add_node("tool_node", tool_node)

# 3. Add Edges
workflow.add_edge(START, "agent")

# Conditional edge from agent to [tool_node, human_review_node, END]
workflow.add_conditional_edges(
    "agent",
    route_tools,
    {
        "tool_node": "tool_node",
        "human_review_node": "human_review_node",
        "__end__": END,
    },
)

# Edge from human_review_node to tool_node (after approval)
# workflow.add_edge("human_review_node", "tool_node")
# Changed to Conditional Edge:
workflow.add_conditional_edges(
    "human_review_node",
    check_approval,
    {"tool_node": "tool_node", "rejection_node": "rejection_node"},
)

# Edge from tool_node back to agent (to interpret results)
workflow.add_edge("tool_node", "agent")

# Edge from rejection_node to END
workflow.add_edge("rejection_node", END)

# 4. Compile Graph with Checkpointer
# We need a checkpointer to support interruption/resumption
# checkpointer = MemorySaver()

# Set interrupt_before to stop BEFORE entering the human_review_node
# Actually, the user wants to approve "before delete/publish".
# Our route_tools sends to "human_review_node".
# If we interrupt BEFORE it, the graph stops. The user can then resume.
# When resumed, it will execute 'human_review_node' (which does nothing) and then go to 'tool_node'.
graph = workflow.compile(interrupt_before=["human_review_node"])


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "thread-1"}}
    response = graph.invoke(
        {"messages": "查看一下system命名空间的内容,Test环境,appid为invoice-ws-priv"},
        config=config,
    )
    print(response)
