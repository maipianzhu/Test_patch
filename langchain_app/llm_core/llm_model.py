import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek


# 0. 加载环境配置
load_dotenv()

# 检查 API Key
if not os.getenv("DEEPSEEK_API_KEY"):
    print("❌ 错误: 未找到 DEEPSEEK_API_KEY，请确保 .env 文件已配置。")
    exit(1)

# 1. 基础用法: 初始化模型
llm = ChatDeepSeek(
    model="deepseek-chat",  # 或者 "deepseek-coder"
    temperature=0.3,  # 温度越低越严谨
    max_tokens=1024,
)
