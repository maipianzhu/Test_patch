import os
from typing import Literal

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

# 0. 加载环境配置
load_dotenv()


# 2. 定义工具 (模拟敏感操作)
@tool
def send_email(recipient: str, content: str):
    """发送邮件给指定收件人。仅在获得明确批准后执行。"""
    # 实际业务中这里是发送邮件的逻辑
    return f"已成功发送邮件给 {recipient}，内容: {content}"


tools = [send_email]
tool_node = ToolNode(tools)

# 3. 设置 LLM
llm = ChatDeepSeek(
    model="deepseek-chat",  # 或者 "deepseek-coder"
    temperature=0.3,  # 温度越低越严谨
    max_tokens=1024,
)

llm_with_tools = llm.bind_tools(tools)


# 4. 定义图节点逻辑
def agent_node(state: MessagesState):
    """代理节点：负责思考和生成工具调用请求"""
    messages = state["messages"]
    result = llm_with_tools.invoke(messages)
    return {"messages": [result]}


def should_continue(state: MessagesState) -> Literal["tools", END]:
    """条件边：判断是执行工具还是结束"""
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END


# 5. 构建 LangGraph
builder = StateGraph(MessagesState)

# 添加节点
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)

# 添加边
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue)
builder.add_edge("tools", "agent")

# === 关键点：设置 Checkpointer 和 中断 ===
# MemorySaver 用于在内存中保存状态，生产环境通常使用 PostgresSaver
checkpointer = MemorySaver()

# interrupt_before=["tools"]: 在进入 "tools" 节点前暂停
# 这意味着 AI 生成了工具调用请求，但工具还没真正执行
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"]
)


# 6. 模拟 Human-in-the-loop 运行流程
def run_interactive_session():
    # thread_id 是区分不同会话的关键
    thread_config = {"configurable": {"thread_id": "session_1"}}

    print("--- 开始对话 ---")
    user_input = "帮我给老板发个邮件，说我明天请病假。"

    # 第一步：运行直到遇到中断
    print(f"User: {user_input}")

    # stream_mode="values" 会流式输出状态更新
    for event in graph.stream({"messages": [HumanMessage(content=user_input)]}, thread_config, stream_mode="values"):
        event["messages"][-1].pretty_print()

    # 此时，代码执行暂停了。检查当前状态
    snapshot = graph.get_state(thread_config)

    if snapshot.next:
        print("\n--- 🛑 系统暂停：检测到即将执行敏感操作 ---")
        # 获取 AI 想要执行的动作
        last_message = snapshot.values["messages"][-1]
        if last_message.tool_calls:
            tool_call = last_message.tool_calls[0]
            print(f"AI 申请调用工具: {tool_call['name']}")
            print(f"参数: {tool_call['args']}")

            # === Human Loop 交互部分 ===
            decision = input("\n人类管理员: 是否批准操作? (y/n/update): ").strip().lower()

            if decision == 'y':
                print("--- ✅ 操作已批准，继续执行 ---")
                # 传入 None 表示继续之前的状态，不做修改
                for event in graph.stream(None, thread_config, stream_mode="values"):
                    event["messages"][-1].pretty_print()

            elif decision == 'n':
                print("--- ❌ 操作被拒绝，向 AI 提供反馈 ---")
                # 我们向状态中注入一条“工具执行失败/被拒绝”的消息
                # 或者直接作为 HumanMessage 告诉 AI 不要这么做
                feedback_msg = "管理员拒绝了该操作。请询问用户是否需要修改邮件内容。"

                # update_state 可以修改图的记忆
                graph.update_state(
                    thread_config,
                    {"messages": [HumanMessage(content=feedback_msg)]},
                    as_node="agent"  # 假装这是在 agent 节点之后发生的
                )

                # 恢复执行，AI 会看到新的反馈
                for event in graph.stream(None, thread_config, stream_mode="values"):
                    event["messages"][-1].pretty_print()

            elif decision == 'update':
                print("--- ✏️  修改参数 ---")
                # 高级用法：直接修改工具调用的参数
                new_content = input("请输入新的邮件内容: ")
                tool_call['args']['content'] = new_content

                # 更新最后一条 AI 消息（覆盖之前的工具调用）
                graph.update_state(
                    thread_config,
                    {"messages": [last_message]},
                )
                print("--- 参数已修改，批准执行 ---")
                for event in graph.stream(None, thread_config, stream_mode="values"):
                    event["messages"][-1].pretty_print()

    print("\n--- 流程结束 ---")


if __name__ == "__main__":
    run_interactive_session()
