import streamlit as st
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # 自动读取 .env


# Add project root to sys.path to allow imports from langGraph_app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langGraph_app.agent import graph

# Page Config
st.set_page_config(page_title="Apollo AI Assistant", layout="wide")
st.title("🚀 Apollo Intelligent Configuration Assistant")

# Sidebar for Config
with st.sidebar:
    st.header("Settings")
    thread_id = st.text_input("Thread ID", value="thread-1")
    if st.button("Clear History"):
        # We can't easily clear backend memory without a specific function,
        # but we can clear UI state.
        st.session_state.messages = []
        st.rerun()

# Initialize State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Config for Graph
config = {"configurable": {"thread_id": thread_id}}


def render_messages():
    # Debug: Show message types in sidebar
    with st.sidebar:
        with st.expander("Debug: Message History"):
            for i, m in enumerate(st.session_state.messages):
                st.write(f"**Msg {i}:** {type(m).__name__}")
                st.code(m.content[:100])
                if hasattr(m, "tool_calls"):
                    st.write(f"Tool Calls: {m.tool_calls}")

    for msg in st.session_state.messages:
        # Determine Role and Content
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.write(msg.content)
        elif isinstance(msg, AIMessage):
            # If AI message has content, show it.
            # If it has tool_calls but no content, we might want to show "Executing..." or hide it.
            if msg.content:
                with st.chat_message("assistant"):
                    st.write(msg.content)
            elif msg.tool_calls:
                with st.chat_message("assistant"):
                    st.write(f"🔄 Requesting Tool: `{msg.tool_calls[0]['name']}`")
        elif isinstance(msg, ToolMessage):
            # Tool output is definitely "assistant" side info
            with st.chat_message("assistant"):
                st.markdown("### 🛠️ Tool Result")
                st.markdown(msg.content)
        else:
            # Fallback for other message types
            with st.chat_message("assistant"):
                st.write(f"[{type(msg).__name__}]: {msg.content}")


# 1. Display Chat History
render_messages()

# 2. Check for Pending Approval (Graph Interruption)
# We check the CURRENT state of the graph for this thread.
try:
    current_state = graph.get_state(config)
    # Check if we are paused at 'human_review_node'
    if current_state.next and "human_review_node" in current_state.next:
        # Get the tool call info from the last message
        last_msg = current_state.values["messages"][-1]
        tool_call = last_msg.tool_calls[0] if last_msg.tool_calls else None

        with st.container(border=True):
            st.warning("⚠️ **Approval Required**")
            st.markdown(f"The agent wants to execute: **`{tool_call['name']}`**")
            st.json(tool_call["args"])

            col1, col2 = st.columns(2)
            if col1.button("✅ Approve"):
                with st.spinner("Approving and Resuming..."):
                    # Update state with approval
                    graph.update_state(config, {"approval": "yes"})
                    # Resume graph
                    events = graph.stream(None, config, stream_mode="values")
                    for event in events:
                        if "messages" in event:
                            # In values mode, event["messages"] is the list of params?
                            # Actually usually it yields the full state or updates.
                            # We just wait for it to finish.
                            pass

                    # Refresh UI
                    # Sync UI messages with Backend
                    final_state = graph.get_state(config)
                    st.session_state.messages = final_state.values.get("messages", [])
                    st.rerun()

            if col2.button("🛑 Reject"):
                with st.spinner("Rejecting..."):
                    # Update state with rejection
                    graph.update_state(config, {"approval": "no"})
                    # Resume graph
                    events = graph.stream(None, config, stream_mode="values")
                    for event in events:
                        pass

                    # Refresh UI
                    final_state = graph.get_state(config)
                    st.session_state.messages = final_state.values.get("messages", [])
                    st.rerun()

        # If pending approval, we stop here to avoid confusion (or allow chatting? typically blocking).
        # We can stop input if we want strict modal behavior.

except Exception as e:
    # E.g. Config not found or new thread
    pass


# 3. Chat Input
if user_input := st.chat_input("Tell me what to configure..."):
    # Add User Message to UI
    user_msg = HumanMessage(content=user_input)
    st.session_state.messages.append(user_msg)
    with st.chat_message("user"):
        st.write(user_input)

    # Process with Agent
    with st.chat_message("assistant"):
        with st.spinner("Agent is thinking..."):
            try:
                # Stream the response
                # We use stream() to let it run until end or interruption
                inputs = {"messages": [user_msg]}

                # Stream events usually return the state updates.
                # simpler to use invoke if we don't implement full token streaming UI here.
                # Use invoke for simplicity first.

                # Note: invoke returns the FINAL state value usually.
                # If interrupted, it stops.

                # We need to handle 'recursion_limit' if loop is long, but defaults are usually ok.
                final_res = graph.invoke(inputs, config)

                # Update UI history from backend state
                st.session_state.messages = final_res["messages"]
                st.rerun()

            except Exception as e:
                import traceback

                st.error(f"❌ Execution Error: {e}")
                st.code(traceback.format_exc())
                # Do NOT rerun immediately on error, look at the error first.
