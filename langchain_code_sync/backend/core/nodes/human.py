from typing import Any, Dict
from core.state import SyncState
from services.git_manager import PatchManager, DiscoveryManager


def human_review_node(state: SyncState) -> Dict[str, Any]:
    """
    人工审查节点：
    其实际逻辑非常简单，因为复杂的操作发生在工作流“挂起”期间。
    当用户通过 UI 完成代码修改并点击“提交”时，工作流会从这里继续。
    """

    # 既然能运行到这一行，说明用户已经通过 UI 解决了冲突
    # 我们将冲突状态重置，准备进入下一个 patch 的应用
    return {
        "has_conflict": False,
        "conflicts": [],
        "status": "applying",
        "logs": state["logs"] + ["人工合并完成，继续应用下一个补丁。"],
    }


def push_approval_node(state: SyncState):
    pm = PatchManager(state["repo_a_dir"], state["repo_b_dir"])
    dm = DiscoveryManager(state["repo_a_dir"], state["repo_b_dir"])

    try:
        # 1. 记录日志
        logs = state["logs"] + ["正在执行最终同步对齐并推送..."]

        # 2. 对齐元数据到 Repo A 的最新远程 HEAD
        latest_a_id = dm.get_remote_head()
        dm.save_metadata(latest_a_id)

        # 3. 提交元数据变更 (如果存在)
        pm._run_git_text(["add", ".sync_metadata.json"], state["repo_b_dir"])
        status_out = pm._run_git_text(["status", "--porcelain"], state["repo_b_dir"])
        if ".sync_metadata.json" in status_out:
            pm._run_git_text(
                [
                    "commit",
                    "-m",
                    f"chore: sync metadata alignment to {latest_a_id[:8]}",
                ],
                state["repo_b_dir"],
            )

        # 4. 执行真正的推送
        pm.push_to_remote()

        return {
            "status": "completed",
            "logs": logs + [f"🚀 最终同步完成，已对齐至 {latest_a_id[:8]}"],
        }
    except Exception as e:
        return {"status": "error", "logs": state["logs"] + [f"❌ 推送失败: {str(e)}"]}
