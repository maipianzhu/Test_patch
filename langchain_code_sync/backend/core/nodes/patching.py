from typing import Any, Dict
from core.state import SyncState

# 关键：统一在顶部导入
from services.git_manager import PatchManager, DiscoveryManager


def apply_patch_node(state: SyncState) -> Dict[str, Any]:
    idx = state["current_commit_index"]
    pending = state["pending_commits"]

    # --- 1. 立即初始化所有 Manager，确保任何分支都能访问 ---
    pm = PatchManager(state["repo_a_dir"], state["repo_b_dir"])
    dm = DiscoveryManager(state["repo_a_dir"], state["repo_b_dir"])
    # 确保 dm 内部的元数据路径已经更新为物理路径
    dm._update_paths(state["repo_a_dir"], state["repo_b_dir"])

    # --- 2. 检查任务是否已经完成 ---
    if idx >= len(pending):
        try:
            # 获取 Repo A 真正的远程 HEAD (311eb8d)
            latest_a_id = dm.get_remote_head()
            # 保存到指纹文件，确保下次同步对齐
            dm.save_metadata(latest_a_id)

            # 推送到远程 Repo B
            pm.push_to_remote()

            return {
                **state,
                "status": "completed",
                "logs": state["logs"]
                + [f"🚀 所有补丁同步完成，终点对齐至: {latest_a_id[:8]}"],
            }
        except Exception as e:
            return {
                **state,
                "status": "error",
                "logs": state["logs"]
                + [f"❌ 任务完成，但在推送或保存元数据时出错: {str(e)}"],
            }

    # --- 3. 正常应用补丁逻辑 ---
    current_cid = pending[idx]

    # 获取元数据
    metadata = pm.get_commit_metadata(current_cid)

    # 生成并应用补丁
    patch_bytes = pm.generate_patch(current_cid)
    success, error_log = pm.apply_patch_attempt(patch_bytes)

    if success:
        # 应用成功：提交并记录作者历史
        pm.commit_with_metadata(metadata)
        # 单步更新元数据文件
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
            print(f"DEBUG: Error Log -> {error_log}")
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
