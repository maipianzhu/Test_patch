from langchain_core.messages import ToolMessage, AIMessage
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
from langsmith import Client
from langGraph_app.utils.state import AgentState
from langGraph_app.utils.tools import (
    get_apollo_config,
    create_apollo_item,
    update_apollo_item,
    delete_apollo_item,
    publish_apollo_release,
    batch_add_apollo_config,
)
from langchain_deepseek import ChatDeepSeek
import os

# Define the tools
tools = [
    get_apollo_config,
    create_apollo_item,
    update_apollo_item,
    delete_apollo_item,
    publish_apollo_release,
    batch_add_apollo_config,
]

# 0. 加载环境配置
load_dotenv()

client = Client(api_key=os.getenv("LANGCHAIN_API_KEY"))
# prompt = client.pull_prompt("apollo-opt", include_model=False)

llm = ChatDeepSeek(model="deepseek-chat", temperature=0)

# agent = create_agent(llm, tools)

# chain = prompt | llm.bind_tools(tools)
llm = llm.bind_tools(tools)


def agent_node(state: AgentState):
    """
    Invokes the agent model to generate a response or tool calls.
    """
    messages = state["messages"]
    # Pass a dictionary because the prompt template expects the 'messages' key
    response = llm.invoke(messages)
    # response = agent.invoke({"messages": messages})

    return {"messages": [response]}


def human_review_node(state: AgentState):
    """
    This node serves as a checkpoint for human review.
    It doesn't modify the state but allows the graph to stop here.
    """
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        tool_call = last_message.tool_calls[0]
        # User requested: Prompt then ask.
        # Since we interrupt before this node, this print serves as a log when resuming (or before if we move interrupt).
        # But primarily, the Client (UI) handles the prompt.
        print(
            f"🛑 [Nodes] Reviewing operation: {tool_call['name']} - {tool_call['args']}"
        )
        print("❓ Approval needed. Please update state with 'approval': 'yes'/'no'.")
    pass


def rejection_node(state: AgentState):
    """
    Called when the user rejects the operation.
    We MUST send a ToolMessage for each pending tool_call_id to satisfy LLM API requirements.
    """
    last_message = state["messages"][-1]
    tool_messages = []

    if last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_messages.append(
                ToolMessage(
                    content="Operation rejected by user.", tool_call_id=tool_call["id"]
                )
            )

    return {
        "messages": tool_messages
        + [AIMessage(content="⛔ Operation rejected by user.")]
    }


def check_approval(state: AgentState):
    """
    Check if the operation was approved.
    """
    approval = state.get("approval", "").lower()
    if approval == "yes":
        return "tool_node"
    else:
        return "rejection_node"


# Standard ToolNode
tool_node = ToolNode(tools)


def route_tools(state: AgentState):
    """
    Determine the next node based on the agent's last message.
    """
    messages = state["messages"]
    last_message = messages[-1]

    if not last_message.tool_calls:
        print("🔀 [Route] No tool calls -> END")
        return "__end__"

    # Check for sensitive tools
    sensitive_tools = [
        "delete_apollo_item",
        "publish_apollo_release",
        "batch_add_apollo_config",
    ]
    for tool_call in last_message.tool_calls:
        print(f"🔀 [Route] Checking tool: {tool_call['name']}")
        if tool_call["name"] in sensitive_tools:
            print("🔀 [Route] Sensitive tool detected -> human_review_node")
            return "human_review_node"

    print("🔀 [Route] Safe tool -> tool_node")
    return "tool_node"
