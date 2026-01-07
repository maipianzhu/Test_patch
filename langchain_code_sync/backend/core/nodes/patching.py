from typing import Any, Dict
from core.state import SyncState
from services.git_manager import PatchManager, DiscoveryManager


def apply_patch_node(state: SyncState) -> Dict[str, Any]:
    """
    核心循环：尝试应用当前索引指向的补丁
    """
    # 检查是否已经处理完所有补丁
    idx = state["current_commit_index"]
    if idx >= len(state["pending_commits"]):
        return {"status": "completed"}

    # 初始化 Service
    pm = PatchManager(state["repo_a_dir"], state["repo_b_dir"])
    dm = DiscoveryManager(state["repo_a_dir"], state["repo_b_dir"])

    current_cid = state["pending_commits"][idx]

    # 1. 生成补丁内容
    patch_content = pm.generate_patch(current_cid)

    # 2. 尝试应用补丁 (内部执行 git apply --3way)
    success = pm.apply_patch_attempt(patch_content)

    if success:
        # 情况 A: 应用成功
        # 自动执行 git add/commit 并更新元数据
        pm.commit_applied_patch(current_cid)
        dm.save_metadata(current_cid)  # 更新 B 库中的同步标记

        return {
            "current_commit_index": idx + 1,
            "has_conflict": False,
            "status": "applying",
            "logs": state["logs"] + [f"成功应用补丁: {current_cid[:8]}"],
        }
    else:
        # 情况 B: 发生冲突
        # 1. 获取所有冲突文件
        conflict_files = pm.get_conflict_files()

        # 2. 提取每个冲突文件的 Stage 1, 2, 3 内容 (Base, Ours, Theirs)
        conflict_details = []
        for file_path in conflict_files:
            contents = pm.get_three_way_content(file_path)
            conflict_details.append(
                {
                    "file_path": file_path,
                    "base_content": contents["base"],
                    "ours_content": contents["ours"],
                    "theirs_content": contents["theirs"],
                    "ai_suggestion": None,  # 留给下一个节点 ai_resolve 处理
                }
            )

        return {
            "has_conflict": True,
            "conflicts": conflict_details,
            "status": "conflicted",
            "logs": state["logs"]
            + [f"补丁冲突: {current_cid[:8]}，涉及 {len(conflict_files)} 个文件"],
        }
