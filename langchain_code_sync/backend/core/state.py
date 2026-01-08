from typing import List, Optional, TypedDict
from typing_extensions import Annotated


class ConflictDetail(TypedDict):
    file_path: str
    base_content: str  # 虚拟祖先的内容
    ours_content: str  # RepoB 的内容
    theirs_content: str  # RepoA (Patch) 的内容
    ai_suggestion: Optional[str]  # AI 预处理的结果


class SyncState(TypedDict):
    # 仓库基础信息
    repo_a_dir: str
    repo_b_dir: str

    # 同步元数据
    base_commit: Optional[str]  # 确定的起点 Commit ID
    pending_commits: List[str]  # 待应用的 Commit ID 列表
    current_commit_index: int  # 当前处理到第几个

    # 冲突管理
    has_conflict: bool
    conflicts: List[ConflictDetail]  # 当前补丁产生的冲突列表

    # 流程控制
    status: str  # "analyzing", "applying", "conflicted", "completed", "error"
    logs: List[str]
    push_summary: Optional[str]
