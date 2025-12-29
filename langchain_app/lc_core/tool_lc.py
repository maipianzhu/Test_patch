from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain_app.llm_core.llm_model import llm


@tool
def search(query: str) -> str:
    """搜索信息"""
    return f"搜索结果:{query}"


@tool
def get_weather(location: str) -> str:
    """获取位置天气信息"""
    return f"{location}的天气十分晴朗,1000HF"


agent = create_agent(llm, tools=[search, get_weather])


# 测试
if __name__ == "__main__":
    # 直接传入查询字符串
    response = agent.invoke("成都的天气如何")

    # 打印AI的回复
    print("\n=== Agent 响应 ===")
    print(response)
