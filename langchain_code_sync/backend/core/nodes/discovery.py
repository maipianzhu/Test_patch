from typing import Any, Dict
from core.state import SyncState
from services.git_manager import DiscoveryManager


def discover_origin_node(state: SyncState) -> Dict[str, Any]:
    # 这里的 dm 初始时拿的是 URL
    dm = DiscoveryManager(state["repo_a_dir"], state["repo_b_dir"])
    logs = state.get("logs", [])

    try:
        # 【第一步】调用转换逻辑，拿到 Hash 后的物理路径
        local_a = dm.ensure_local_repo(state["repo_a_dir"], "repo_a")
        local_b = dm.ensure_local_repo(state["repo_b_dir"], "repo_b")

        # 【第二步】非常重要！！
        # 更新 dm 内部的路径为物理路径，否则 dm.find_best_match() 还会去读 URL 导致报错
        dm._update_paths(local_a, local_b)

        logs.append(f"✅ 仓库已定位至本地 Hash 目录")

        # 【第三步】现在执行 Git 操作，cwd 就会是 local_a，不再是 URL
        base_commit = dm.load_metadata()

        if not base_commit:
            logs.append("未发现同步记录，正在扫描指纹...")
            base_commit, score = dm.find_best_match()
            logs.append(f"识别起点: {base_commit[:8]} (匹配度: {score:.2%})")
        else:
            logs.append(f"从指纹文件加载起点: {base_commit[:8]}")

        pending = dm.get_pending_commits(base_commit)

        # 【第四步】将物理路径返回给 state
        # 这样以后所有的节点（patching, ai_resolve）看到的 repo_a_dir 都是物理路径了
        return {
            **state,
            "repo_a_dir": local_a,  # 覆盖 URL
            "repo_b_dir": local_b,  # 覆盖 URL
            "base_commit": base_commit,
            "pending_commits": pending,
            "status": "applying" if pending else "completed",
            "logs": logs + [f"发现 {len(pending)} 个提交"],
        }
    except Exception as e:
        return {**state, "status": "error", "logs": logs + [f"❌ 错误: {str(e)}"]}
