import os
from langchain_core.messages import SystemMessage
from langchain_code_sync.utils.state import AgentState
from langchain_code_sync.utils.patch_generator_tool import sync_tool


def generate_patches(state: AgentState):
    """Generates patches from source repo."""
    output_dir = state["patch_dir"]
    try:
        result = sync_tool.generate_incremental_patches(
            state["source_repo_path"],
            state["target_repo_path"],
            output_dir,
            start_commit_id=state.get("start_commit_id"),
        )
        if "成功生成" in result:
            # Get list of .patch files, sorted
            patches = sorted(
                [
                    os.path.join(output_dir, f)
                    for f in os.listdir(output_dir)
                    if f.endswith(".patch")
                ]
            )
            return {"patches": patches, "current_patch_index": 0}
        else:
            # Handle no patches or error
            if "没有检测到差异" in result:
                return {"patches": [], "current_patch_index": 0}
            print(f"Error generating patches: {result}")
            return {"patches": [], "current_patch_index": 0}

    except Exception as e:
        print(f"Exception generating patches: {e}")
        return {"patches": [], "current_patch_index": 0}


def apply_next_patch(state: AgentState):
    """Applies the next patch in the queue."""
    patches = state.get("patches", [])
    index = state.get("current_patch_index", 0)

    if index >= len(patches):
        return {"current_patch_index": index}  # No more patches

    current_patch = patches[index]
    success, message = sync_tool.apply_patch(state["target_repo_path"], current_patch)

    if success:
        return {"current_patch_index": index + 1, "conflict_error": None}
    else:
        return {"conflict_error": message}


def analyze_conflict(state: AgentState):
    """Analyzes the conflict and provides a suggestion."""
    # Simple logic for now: suggest manual review if failed
    error_msg = state.get("conflict_error", "Unknown error")

    # Check for specific conflict files
    has_rej, conflict_files = sync_tool.check_verify_conflict(state["target_repo_path"])

    conflict_info = ""
    if has_rej:
        conflict_info = "\nConflict Files (.rej):\n" + "\n".join(conflict_files)

    suggestion = (
        f"Conflict detected when applying patch: {state['patches'][state['current_patch_index']]}\n"
        f"Error: {error_msg}\n"
        f"{conflict_info}\n"
        "Suggestion: Review valid .rej files or use git status to see conflicts.\n"
        "Options:\n"
        "1. 'skip': Skip this patch (may cause inconsistency)\n"
        "2. 'retry': Retry applying (if you manually fixed it)\n"
        "3. 'abort': Stop the sync process\n"
    )
    return {
        "agent_suggestion": suggestion,
        "conflict_files": conflict_files if has_rej else [],
    }


def process_user_decision(state: AgentState):
    """Processes the user's decision from the human interaction."""
    decision = state.get("user_decision", "").lower()

    if decision == "skip":
        # Move to next patch
        return {
            "current_patch_index": state["current_patch_index"] + 1,
            "conflict_error": None,
            "agent_suggestion": None,
        }
    elif decision == "retry":
        # Stay on same index, clear error to try again
        return {"conflict_error": None, "agent_suggestion": None}
    elif decision == "abort":
        # Logic to stop graph would be handled by edge condition usually,
        # but here we can just ensure we don't increment and maybe set a flag or just handle in edges.
        # For simplicity, let's treat abort as clearing patches so it ends.
        return {"patches": []}
    else:
        # Default behavior: treat as retry or wait?
        return {
            "agent_suggestion": "Invalid option. Please choose 'skip', 'retry', or 'abort'."
        }
