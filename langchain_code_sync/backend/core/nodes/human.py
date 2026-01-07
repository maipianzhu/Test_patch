from typing import Any, Dict
from core.state import SyncState


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
