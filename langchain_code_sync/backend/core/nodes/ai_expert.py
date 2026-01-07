from typing import Any, Dict, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from core.state import SyncState, ConflictDetail
from langchain_deepseek import ChatDeepSeek
import os


def ai_resolve_node(state: SyncState) -> Dict[str, Any]:
    """
    AI 决策节点：尝试自动解决冲突或生成建议
    """
    # 1. 初始化大模型
    llm = ChatDeepSeek(
        model="deepseek-chat", temperature=0, api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    updated_conflicts = []
    resolved_count = 0

    state["logs"].append("AI 正在分析冲突并尝试自动合并...")

    for conflict in state["conflicts"]:
        # 2. 调用 AI 专家进行合并
        result = _ask_ai_to_merge(llm, conflict)

        # 3. 处理 AI 的结果
        if result["can_auto_resolve"] and result["merged_content"]:
            # 如果 AI 信心十足，我们更新建议内容
            conflict["ai_suggestion"] = result["merged_content"]
            # 注意：这里我们并不直接覆盖文件，而是把 AI 结果放在 suggestion 里
            # 这样在 UI 的中间栏可以默认填充这个结果，由人工做最后确认
            resolved_count += 1
        else:
            conflict["ai_suggestion"] = "AI 无法自动合并，请人工裁决。"

        updated_conflicts.append(conflict)

    # 如果所有冲突都被 AI 解决了（信心满分），我们可以在日志里标记
    log_msg = (
        f"AI 分析完成：{resolved_count}/{len(updated_conflicts)} 个冲突已给出合并建议。"
    )

    return {
        "conflicts": updated_conflicts,
        "logs": state["logs"] + [log_msg],
        # 这里我们依然保持 has_conflict=True，强制进入 human_review 节点
        # 除非你非常信任 AI，可以直接返回 has_conflict=False
        "has_conflict": True,
    }


def _ask_ai_to_merge(llm: ChatDeepSeek, conflict: ConflictDetail) -> Dict:
    """
    私有方法：构造 Prompt 并调用 LLM
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一位资深软件架构师，精通 Git 三路合并逻辑。
你的任务是分析代码冲突，并尝试合并它们。
我们会给你三个版本：
1. Base: 冲突发生前的共同祖先代码。
2. Ours: 当前仓库 (RepoB) 中的代码。
3. Theirs: 补丁 (RepoA) 想要引入的修改。

请遵循以下规则：
- 如果两处修改不冲突（例如修改了不同行），请合并它们。
- 如果是一端增加了注释，另一端修改了逻辑，请保留两者。
- 如果两端修改了同一行逻辑，且你无法确定意图，请标记为不可自动合并。
- 你的输出必须是 JSON 格式。""",
            ),
            (
                "human",
                """
文件路径: {file_path}

<<< BASE CONTENT >>>
{base}

<<< OURS CONTENT (Current RepoB) >>>
{ours}

<<< THEIRS CONTENT (Patch from RepoA) >>>
{theirs}

请输出 JSON 格式：
{{
  "can_auto_resolve": bool, 
  "merged_content": "完整的合并后的代码字符串",
  "reason": "简短的合并说明"
}}
""",
            ),
        ]
    )

    chain = prompt | llm | JsonOutputParser()

    try:
        response = chain.invoke(
            {
                "file_path": conflict["file_path"],
                "base": conflict["base_content"],
                "ours": conflict["ours_content"],
                "theirs": conflict["theirs_content"],
            }
        )
        return response
    except Exception as e:
        return {"can_auto_resolve": False, "merged_content": None, "reason": str(e)}
