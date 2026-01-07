from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

# 导入节点函数
from core.nodes.discovery import discover_origin_node
from core.nodes.patching import apply_patch_node
from core.nodes.ai_expert import ai_resolve_node
from core.nodes.human import human_review_node
from core.state import SyncState


def create_sync_graph():
    # 1. 初始化状态图，传入我们定义的 SyncState 结构
    workflow = StateGraph(SyncState)

    # 2. 注册所有节点
    workflow.add_node("discovery", discover_origin_node)  # 找起点
    workflow.add_node("apply_patch", apply_patch_node)  # 试应用补丁
    workflow.add_node("ai_resolve", ai_resolve_node)  # AI 预处理冲突
    workflow.add_node("human_review", human_review_node)  # 人工干预点

    # 3. 设置入口点
    workflow.set_entry_point("discovery")

    # 4. 定义简单连线 (线性执行)
    workflow.add_edge("discovery", "apply_patch")

    # 5. 定义条件路由 (最核心的决策逻辑)
    def router_after_patch(state: SyncState):
        """决定 apply_patch 之后去哪"""
        if state["status"] == "completed":
            return "end"
        if state["has_conflict"]:
            return "conflict"
        return "next_patch"

    workflow.add_conditional_edges(
        "apply_patch",
        router_after_patch,
        {
            "next_patch": "apply_patch",  # 没冲突，循环应用下一个
            "conflict": "ai_resolve",  # 冲突了，交给 AI 分析
            "end": END,  # 全干完了，结束
        },
    )

    # 6. AI 处理完后，必须经过人工审核断点
    workflow.add_edge("ai_resolve", "human_review")

    # 7. 人工处理完后，回到 apply_patch 检查状态并尝试继续
    workflow.add_edge("human_review", "apply_patch")

    # 8. 【工程核心】配置持久化存储和中断点
    # 使用 SQLite 记录每一时刻的状态，支持服务器重启后恢复
    memory = SqliteSaver.from_conn_string("checkpoints.db")

    # 编译图：在进入 human_review 之前强制中断，等待外部唤醒
    app = workflow.compile(checkpointer=memory, interrupt_before=["human_review"])

    return app
