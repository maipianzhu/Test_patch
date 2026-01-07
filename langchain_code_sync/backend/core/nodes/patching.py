from typing import Any, Dict
from core.state import SyncState

# 关键：统一在顶部导入
from services.git_manager import PatchManager, DiscoveryManager


def apply_patch_node(state: SyncState) -> Dict[str, Any]:
    idx = state["current_commit_index"]
    if idx >= len(state["pending_commits"]):
        pm = PatchManager(state["repo_a_dir"], state["repo_b_dir"])
        try:
            state["logs"].append("正在同步到远程仓库 (Pushing)...")
            pm.push_to_remote()
            return {
                **state,
                "status": "completed",
                "logs": state["logs"] + ["🚀 所有补丁已同步并推送到远程仓库！"],
            }
        except Exception as e:
            return {
                **state,
                "status": "error",
                "logs": state["logs"] + [f"❌ 代码已在本地同步，但推送失败: {str(e)}"],
            }

    # 使用已经导入的 PatchManager
    pm = PatchManager(state["repo_a_dir"], state["repo_b_dir"])
    current_cid = state["pending_commits"][idx]

    # 1. 获取原提交信息
    metadata = pm.get_commit_metadata(current_cid)

    # 2. 生成并尝试应用补丁
    patch_content = pm.generate_patch(current_cid)
    success, error_log = pm.apply_patch_attempt(patch_content)

    if success:
        # 3. 提交代码并保留作者历史
        pm.commit_with_metadata(metadata)

        # 4. 更新元数据 (使用顶部导入的 DiscoveryManager)
        dm = DiscoveryManager(state["repo_a_dir"], state["repo_b_dir"])
        dm.save_metadata(current_cid)

        return {
            **state,
            "current_commit_index": idx + 1,
            "has_conflict": False,
            "status": "applying",
            "logs": state["logs"] + [f"✅ 同步完成: {metadata['message'][:40]}..."],
        }
    else:
        # 5. 冲突处理逻辑
        conflict_files = pm.get_conflict_files()

        # 如果 apply 失败了，但 git 并没有在索引中生成未合并文件
        if not conflict_files:
            # 打印前 10 行补丁内容，检查文件路径是否正确
            print(f"DEBUG: Patch Head -> {patch_content[:500]}")
            return {
                **state,
                "status": "error",
                "logs": state["logs"]
                + [f"❌ 补丁应用彻底失败（无法自动处理）: {error_log[:200]}"],
            }

        # 提取冲突内容供 UI 显示
        all_conflicts = []
        for f_path in conflict_files:
            three_way = pm.get_three_way_content(f_path)
            all_conflicts.append(
                {
                    "file_path": f_path,
                    "base_content": three_way["base"],
                    "ours_content": three_way["ours"],
                    "theirs_content": three_way["theirs"],
                    "ai_suggestion": None,
                }
            )

        return {
            **state,
            "has_conflict": True,
            "conflicts": all_conflicts,
            "status": "conflicted",
            "logs": state["logs"] + [f"🚧 冲突发生: {current_cid[:8]}，请人工裁决"],
        }
