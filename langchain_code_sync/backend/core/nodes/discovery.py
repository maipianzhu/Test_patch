from typing import Any, Dict
from core.state import SyncState
from services.git_manager import DiscoveryManager


def discover_origin_node(state: SyncState) -> Dict[str, Any]:
    # 1. 初始化临时管理器用于处理路径
    # 注意：此时 state["repo_a_dir"] 可能是 URL
    temp_dm = DiscoveryManager(state["repo_a_dir"], state["repo_b_dir"])

    logs = state.get("logs", [])
    logs.append("正在准备本地工作目录...")

    try:
        # 2. 确保 A 和 B 都在本地
        local_a = temp_dm.ensure_local_repo(state["repo_a_dir"], "repo_a")
        local_b = temp_dm.ensure_local_repo(state["repo_b_dir"], "repo_b")

        # 3. 重新实例化 dm 使用本地绝对路径
        dm = DiscoveryManager(local_a, local_b)

        # 4. 寻找起点
        base_commit = dm.load_metadata()
        if not base_commit:
            logs.append("未发现同步记录，正在扫描指纹寻找起点...")
            base_commit, score = dm.find_best_match()
            logs.append(f"识别到虚拟祖先: {base_commit[:8]} (匹配度: {score:.2%})")
        else:
            logs.append(f"从元数据加载起点: {base_commit[:8]}")

        # 5. 定义 pending_commits (解决你报错的关键)
        pending_commits = dm.get_pending_commits(base_commit)
        logs.append(f"发现 {len(pending_commits)} 个待同步提交")

        # 6. 返回更新后的状态
        return {
            **state,
            "repo_a_dir": local_a,  # 更新为本地路径，供后续 patching 节点使用
            "repo_b_dir": local_b,
            "base_commit": base_commit,
            "pending_commits": pending_commits,
            "current_commit_index": 0,
            "status": "applying" if pending_commits else "completed",
            "logs": logs,
        }

    except Exception as e:
        logs.append(f"发现异常: {str(e)}")
        return {**state, "status": "error", "logs": logs}
