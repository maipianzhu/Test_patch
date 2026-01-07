import streamlit as st
import os
import sys

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_code_sync.agent import app


st.set_page_config(page_title="LangChain Code Sync", layout="wide")

st.title("🔄 LangChain Git Sync Agent")

# --- Sidebar Configuration ---
st.sidebar.header("Configuration")
source_repo = st.sidebar.text_input(
    "Source Repo Path (Repo A)", "/tmp/test_git_sync/repo_a"
)
target_repo = st.sidebar.text_input(
    "Target Repo Path (Repo B)", "/tmp/test_git_sync/repo_b"
)
patch_dir = st.sidebar.text_input("Patch Directory", "/tmp/test_git_sync/patches")
start_commit_id = st.sidebar.text_input("Start Commit ID (Optional)", "")

if st.sidebar.button("Reset / Clear State"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- Session State Initialization ---
if "agent_state" not in st.session_state:
    st.session_state["agent_state"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "sync_running" not in st.session_state:
    st.session_state["sync_running"] = False
if "current_conflict" not in st.session_state:
    st.session_state["current_conflict"] = None
if "thread_config" not in st.session_state:
    st.session_state["thread_config"] = {"configurable": {"thread_id": "1"}}


# --- Helper Functions ---
def log_message(msg):
    st.session_state["messages"].append(msg)


def run_step(user_input=None):
    """
    Runs the agent one step at a time or loop until interruption.
    LangGraph `app.stream()` is used here.
    """
    current_state = st.session_state.get("agent_state")

    # Initial Start
    if current_state is None:
        initial_state = {
            "source_repo_path": source_repo,
            "target_repo_path": target_repo,
            "patch_dir": patch_dir,
            "patches": [],
            "current_patch_index": 0,
            "conflict_error": None,
            "conflict_files": [],
            "agent_suggestion": None,
            "user_decision": None,
            "start_commit_id": start_commit_id,
        }
        inputs = initial_state
    else:
        # Resume with user input
        if user_input:
            # We need to update the state with the user decision
            # Since we are not using 'interrupt' node explicitly but rather stopping at `process_user_decision` logic manually
            # We essentially re-invoke with updated state.
            current_state["user_decision"] = user_input
            # Clear conflicts
            current_state["conflict_error"] = None
            current_state["conflict_files"] = []
            inputs = current_state
        else:
            inputs = current_state

    log_message(f"🏃‍♂️ Running... (Input: {user_input if user_input else 'Start'})")

    # Stream events
    try:
        # Note: In a real persistent graph, we would use memory checkpointer.
        # Here we are passing state manually for simplicity of demo.
        # If the graph was compiled with checkpointer, we'd pass `thread_config`.
        # Here we pass inputs directly.

        # We need to loop because stream returns one update at a time.
        for output in app.stream(inputs):
            for node_name, state_update in output.items():
                # Update local session state
                if st.session_state["agent_state"] is None:
                    st.session_state["agent_state"] = inputs  # initialize base

                st.session_state["agent_state"].update(state_update)
                new_state = st.session_state["agent_state"]

                log_message(f"✅ Node Completed: **{node_name}**")

                # Check specific node outputs for display
                if node_name == "generate_patches":
                    count = len(new_state.get("patches", []))
                    log_message(f"📝 Generated {count} patches.")

                if node_name == "apply_next_patch":
                    idx = new_state.get("current_patch_index")
                    if new_state.get("conflict_error"):
                        log_message(f"❌ Patch {idx} Failed!")
                    else:
                        log_message(f"✅ Patch {idx} Applied Successfully.")

                if node_name == "analyze_conflict":
                    # Conflict detected! Stop loop and asking for user input.
                    st.session_state["current_conflict"] = {
                        "suggestion": new_state.get("agent_suggestion"),
                        "files": new_state.get("conflict_files", []),
                        "error": new_state.get("conflict_error"),
                    }
                    st.session_state["sync_running"] = False  # Pause UI loop
                    return  # Exit run_step to wait for user

                if node_name == "process_user_decision":
                    decision = new_state.get("user_decision")
                    log_message(f"🤔 User decided: {decision}")
                    # Clear conflict state
                    st.session_state["current_conflict"] = None

        # If loop finishes without returning, we are done
        log_message("🎉 Workflow Completed.")
        st.session_state["sync_running"] = False
        st.session_state["current_conflict"] = None

    except Exception as e:
        st.error(f"Error: {e}")
        st.session_state["sync_running"] = False


# --- Main UI Logic ---

# 1. Start Button
if not st.session_state["sync_running"] and not st.session_state["current_conflict"]:
    if st.button("Start Sync"):
        st.session_state["sync_running"] = True
        st.session_state["messages"] = []  # Clear logs
        st.session_state["agent_state"] = None  # Reset state
        run_step()
        st.rerun()

# 2. Conflict Handling Page / Section
if st.session_state["current_conflict"]:
    st.warning("⚠️ Conflict Detected!")

    conflict = st.session_state["current_conflict"]

    st.markdown("### Agent Suggestion")
    st.info(conflict["suggestion"])

    if conflict["files"]:
        st.markdown(f"### Conflict Files ({len(conflict['files'])})")
        for f in conflict["files"]:
            st.code(f, language="text")

    st.markdown("### Resolve")
    col1, col2, col3 = st.columns(3)

    if col1.button("Skip Patch"):
        run_step("skip")
        st.rerun()

    if col2.button("Retry (Fixed Manually)"):
        run_step("retry")
        st.rerun()

    if col3.button("Abort"):
        run_step("abort")
        st.rerun()

# 3. Running Indicator
if st.session_state["sync_running"] and not st.session_state["current_conflict"]:
    st.spinner("Agent is working...")

# 4. Logs Display
st.markdown("---")
st.subheader("Activity Log")
for msg in st.session_state["messages"]:
    st.markdown(msg)
