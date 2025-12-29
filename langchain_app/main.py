import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek

# 1. 加载 .env 文件 (默认寻找当前或父级目录下的 .env)
# 这一步非常重要，必须在访问 os.getenv 之前执行
load_dotenv()

# 2. 获取 API Key
api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    print("错误：未找到 DEEPSEEK_API_KEY,请检查 .env 文件")
else:
    print(f"成功加载 API Key: {api_key[:5]}******")

    # 3. 初始化 ChatDeepSeek 模型
    # langchain-deepseek 会自动读取环境变量中的 DEEPSEEK_API_KEY
    # 但显式传入也是一个好习惯，或者用于 debug
    llm = ChatDeepSeek(
        model="deepseek-chat",  # 或者是 "deepseek-coder"
        temperature=0.7,
        # api_key=api_key # 如果环境变量已设，这一行其实是可选的
    )

    # 4. 简单测试
    try:
        response = llm.stream("你好,DeepSeek!请做一个简短的自我介绍。")
        print("\n--- 模型回复 ---")
        for chunk in response:
            print(chunk.content, end="")
        print()
    except Exception as e:
        print(f"\n调用模型时出错: {e}")
