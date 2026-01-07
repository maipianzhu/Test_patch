from typing import Any, Dict
from core.state import SyncState
from services.git_manager import DiscoveryManager


def discover_origin_node(state: SyncState) -> Dict[str, Any]:
    """
    第一步：发现同步起点和待同步列表
    """
    # 实例化 service
    dm = DiscoveryManager(state["repo_a_dir"], state["repo_b_dir"])

    # 1. 优先尝试从元数据（.sync_metadata.json）读取上一次同步的位点
    base_commit = dm.load_metadata()
    log_msg = ""

    if not base_commit:
        # 2. 如果是第一次同步，执行指纹对比算法搜索起点
        # 这里可能需要一点时间
        base_commit, score = dm.find_best_match(max_search_depth=200)
        log_msg = (
            f"未发现元数据，通过指纹识别起点: {base_commit[:8]} (相似度: {score:.2%})"
        )
    else:
        log_msg = f"发现同步记录，起点 Commit: {base_commit[:8]}"

    # 3. 计算从 base_commit 到 RepoA 最新提交之间的差异列表
    # --reverse 确保我们是从旧到新一个一个应用补丁
    pending_commits = dm.get_pending_commits(base_commit)

    # 4. 更新状态
    return {
        "base_commit": base_commit,
        "pending_commits": pending_commits,
        "current_commit_index": 0,
        "status": "applying" if pending_commits else "completed",
        "logs": state["logs"] + [log_msg, f"发现 {len(pending_commits)} 个待同步提交"],
    }
