from typing import Any, Dict
from core.state import SyncState
from services.git_manager import PatchManager, DiscoveryManager


def apply_patch_node(state: SyncState) -> Dict[str, Any]:
    with open("debug.log", "a") as f:
        f.write(
            f"DEBUG: Entering apply_patch_node, status={state.get('status')}, index={state.get('current_commit_index')}\n"
        )
    """
    补丁应用节点：负责逐个应用补丁，处理成功提交及冲突提取。
    """
    idx = state["current_commit_index"]
    pending = state["pending_commits"]

    # --- 1. 初始化 Manager (放置在函数顶部，防止 UnboundLocalError) ---
    # 这里的 repo_a_dir 和 repo_b_dir 已经是 discovery 节点转换后的本地物理路径
    pm = PatchManager(state["repo_a_dir"], state["repo_b_dir"])
    dm = DiscoveryManager(state["repo_a_dir"], state["repo_b_dir"])
    # 确保 dm 内部路径已同步（用于 save_metadata）
    dm._update_paths(state["repo_a_dir"], state["repo_b_dir"])

    # --- 2. 检查任务是否已经全部完成 ---
    if idx >= len(pending):
        try:
            state["logs"].append("正在进行最终对齐并推送到远程...")

            # 获取 Repo A 真正的远程 HEAD ID (例如 354b2ceb)
            dm.get_remote_head()

            # A. 仅生成推送摘要供前端展示
            push_summary = pm._run_git_text(
                ["log", "origin/main..HEAD", "--oneline"], state["repo_b_dir"]
            )

            return {
                **state,
                "status": "awaiting_push",  # 变为等待推送状态
                "logs": state["logs"]
                + ["✅ 所有补丁已应用到本地。等待最终推送确认..."],
                "push_summary": push_summary,  # 新增一个状态字段存摘要
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
    state["logs"].append(f"正在处理补丁 ({idx + 1}/{len(pending)}): {current_cid[:8]}")

    # A. 获取原提交元数据（作者、消息）
    metadata = pm.get_commit_metadata(current_cid)

    # B. 生成二进制补丁并尝试应用
    patch_bytes = pm.generate_patch(current_cid)
    success, error_log = pm.apply_patch_attempt(patch_bytes)

    if success:
        # --- 核心改进：调整顺序 ---
        # 1. 先保存元数据到磁盘文件
        dm.save_metadata(current_cid)

        # 2. 再执行 commit（内部包含 git add .）
        # 这样刚才修改的 .sync_metadata.json 就会和代码改动一起被提交
        pm.commit_with_metadata(metadata)

        return {
            **state,
            "current_commit_index": idx + 1,
            "has_conflict": False,
            "status": "applying",
            "logs": state["logs"] + [f"✅ 同步完成: {metadata['message'][:40]}..."],
        }
    else:
        # --- 4. 冲突处理逻辑 ---
        conflict_files = pm.get_conflict_files()

        if not conflict_files:
            # 如果 apply 失败但没产生冲突标记（通常是路径深度或格式问题）
            # 我们选择停下来报错，而不是盲目跳过
            return {
                **state,
                "status": "error",
                "logs": state["logs"] + [f"❌ 补丁应用彻底失败: {error_log[:200]}"],
            }

        # 提取冲突内容供前端三栏编辑器使用
        all_conflicts = []
        for f_path in conflict_files:
            three_way = pm.get_three_way_content(f_path)
            all_conflicts.append(
                {
                    "file_path": f_path,
                    "base_content": three_way["base"],
                    "ours_content": three_way["ours"],
                    "theirs_content": three_way["theirs"],
                    "ai_suggestion": None,  # 留给下一个 ai_expert 节点处理
                }
            )

        return {
            **state,
            "has_conflict": True,
            "conflicts": all_conflicts,
            "status": "conflicted",
            "logs": state["logs"] + [f"🚧 冲突发生于 {current_cid[:8]}，请人工裁决"],
        }
