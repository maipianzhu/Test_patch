import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# 0. 加载环境配置
load_dotenv()

# 检查 API Key
if not os.getenv("DEEPSEEK_API_KEY"):
    print("❌ 错误: 未找到 DEEPSEEK_API_KEY，请确保 .env 文件已配置。")
    exit(1)

print("✅ 环境加载成功，开始 LangChain DeepSeek 使用演示...\n")
print("="*50)

# 1. 基础用法: 初始化模型
print("--- 1. 基础对话 (Invoke) ---")
llm = ChatDeepSeek(
    model="deepseek-chat", # 或者 "deepseek-coder"
    temperature=0.3,       # 温度越低越严谨
    max_tokens=1024, 
    # timeout=60,
    # max_retries=2,
)

response = llm.invoke("用一句话形容 Python 语言的特点。")
print(f"DeepSeek 回复: {response.content}")
print("="*50)


# 2. 流式输出 (Streaming)
# 适合长文本生成，提升用户体验
print("--- 2. 流式输出 (Stream) ---")
print("DeepSeek 正在思考并逐字回复: ", end="", flush=True)

stream = llm.stream("请列出 3 个学习编程的好习惯。")
for chunk in stream:
    print(chunk.content, end="", flush=True)
print("\n" + "="*50)


# 3. 使用 Prompt Template (提示词模板) 和 LCEL 链
# 这是 LangChain 的核心：将 Prompt、Model 和 Parser 串联起来
print("--- 3. Prompt Template + LCEL Chain ---")

# 定义一个翻译任务的模板
prompt = ChatPromptTemplate.from_template(
    "你是一个专业的翻译助手。请将下面的{language}文本翻译成中文：\n\n{text}"
)

# 创建链：Prompt -> Model -> OutputParser (直接提取文本内容)
chain = prompt | llm | StrOutputParser()

english_text = "LangChain makes it easiest to build context-aware reasoning applications."
result = chain.invoke({"language": "英语", "text": english_text})

print(f"原文: {english_text}")
print(f"译文: {result}")
print("="*50)


# 4. 结构化输出 (Structured Output) - JSON 模式
# DeepSeek 支持 JSON Mode，这对于需要程序解析结果的场景非常有用
print("--- 4. 结构化输出 (JSON Mode) ---")

# 方式 A: 使用 .bind(response_format=...) 原生参数
json_llm = llm.bind(response_format={"type": "json_object"})

json_prompt = ChatPromptTemplate.from_messages([
    ("system", "如果不以 JSON 格式输出，用户将无法解析。请务必以 JSON 格式回答，包含 'name', 'age', 'skills' (list) 字段。"),
    ("user", "生成一个虚构的 Python 资深工程师的角色信息。")
])

json_chain = json_prompt | json_llm | StrOutputParser()

print("正在生成 JSON 数据...")
json_result = json_chain.invoke({})
print(json_result)
print("="*50)

print("\n🎉 演示结束！")
