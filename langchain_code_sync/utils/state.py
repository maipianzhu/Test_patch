from typing import TypedDict, List, Optional


class AgentState(TypedDict):
    source_repo_path: str
    target_repo_path: str
    patch_dir: str
    patches: List[str]  # List of patch file paths
    current_patch_index: int
    conflict_error: Optional[str]
    conflict_files: Optional[List[str]]
    agent_suggestion: Optional[str]
    user_decision: Optional[str]
    start_commit_id: Optional[str]
