from langchain.agents import create_agent
from langchain_app.llm_core.llm_model import llm as dp_llm
from langchain.agents.middleware import SummarizationMiddleware, HumanInTheLoopMiddleware, InterruptOnConfig
from langchain_app.lc_core.tool_lc import get_weather
from langgraph.checkpoint.memory import MemorySaver

# ----------------------------预置中间件-------------------------

# 1、摘要 Summarization

summarization_middleware = SummarizationMiddleware(
    model="openai:gpt-4o-mini",  # 用于生成摘要的模型
    trigger=("tokens", 3000),  # 触发摘要的token阈值
    keep=("messages", 20),  # 要保留的最新消息数量
    # token_counter  自定义token计算函数，默认为字符串计数
    # summary_prompt 自定义提示词模版，未指定，使用内置模版
    # summary_prefix 摘要信息前缀
)

summar_agent = create_agent(
    dp_llm,
    middleware=[summarization_middleware],
)

# 2、人为控制 Human-in-the-loop(已转为LangGraph)

human_in_the_loop_middleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "get_weather": InterruptOnConfig(
            allowed_decisions=["approve", "edit", "reject"],
        ),
    }
)

h_agent = create_agent(
    dp_llm,
    tools=[get_weather],
    middleware=[human_in_the_loop_middleware],
    checkpointer=MemorySaver()
)
# 3、缓存

# 4、限制模型调用


# 5、限制工具调用

# 6、模型回退

# 7、PLL 检测

# 8、规划

# 9、LLM工具选择器


# 10、工具重试

# 11、LLM工具模拟器


# 12、上下文编辑

# -----------------------自定义中间件-----------------------


agents = {}
agents["summar_agent"] = summar_agent
agents["human_in_the_loop_middleware"] = h_agent


def handle_human_in_the_loop(agent, config):
    """处理 Human-in-the-loop 交互"""
    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            return

        # 发送用户消息给agent
        response = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config
        )

        # 检查是否有中断需要处理
        snapshot = agent.get_state(config)
        if snapshot.next:
            # 存在中断，需要处理
            print("检测到需要人工审批的操作，请输入 'approve', 'edit' 或 'reject'")
            while True:
                human_decision = input("Human decision: ").lower()
                if human_decision in ["approve", "edit", "reject"]:
                    # 直接继续执行，让agent处理人类决策
                    try:
                        # 使用人类输入作为下一步的输入
                        final_response = agent.invoke(
                            {"human_decision": human_decision},
                            config=config
                        )
                        print("Assistant: ", final_response["messages"][-1].content)
                    except Exception as e:
                        print(f"处理人类决策时出错: {e}")
                    break
                else:
                    print("请输入有效的决策: 'approve', 'edit', 或 'reject'")
        else:
            # 没有中断，直接输出结果
            print("Assistant: ", response["messages"][-1].content)


if __name__ == "__main__":
    print("欢迎,请选择要使用的中间件模型:")
    for key in agents.keys():
        print(key)
    print("exit 退出")

    # 添加固定的线程ID配置
    config = {"configurable": {"thread_id": "1"}}

    while True:
        user_input = input("选择模型: ")

        if user_input == "exit":
            print("bye!!!")
            break
        elif user_input in agents.keys():
            agent = agents[user_input]
            print("正在使用模型: ", user_input, "请输入您的问题:")

            if user_input == "human_in_the_loop_middleware":
                # 使用专门的处理函数处理 Human-in-the-loop
                handle_human_in_the_loop(agent, config)
            else:
                # 其他模型使用原有逻辑
                while True:
                    user_input = input("User: ")
                    if user_input == "exit":
                        break
                    response = agent.invoke(
                        {"messages": [{"role": "user", "content": user_input}]},
                        config=config
                    )
                    # 输出响应内容
                    print("Assistant: ", response["messages"][-1].content)
        else:
            print("未找到该中间件模型")
