from langchain_app.llm_core.llm_model import llm
from langchain.agents import create_agent
from langchain.agents.middleware import (
    wrap_model_call,
    ModelRequest,
    ModelResponse,
    wrap_tool_call,
)
from langchain_core.messages import ToolMessage


agent = create_agent(llm)

# 智能体+动态模型


@wrap_model_call
def dynamic_models_sellection(request: ModelRequest, handler) -> ModelResponse:
    """根据对话内容动态选择模型"""
    message_count = len(request.state["messages"])
    if message_count > 5:
        model = llm
    else:
        model = llm
    request.model = model
    return handler(request)


agent = create_agent(llm, middleware=[dynamic_models_sellection])


# 工具+工具错误处理
@wrap_tool_call
def tool_error_handler(request, handler):
    """使用自定义消息处理工具执行错误。"""
    try:
        return handler(request)
    except Exception as e:
        # 向模型返回自定义错误信息
        return ToolMessage(
            content=f"工具执行错误了,请检查你的输入:{str(e)}",
            tool_call_id=request.tool_call["id"],
        )
