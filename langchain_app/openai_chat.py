from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    print("❌ 错误: 未找到 OPENAI_API_KEY，请确保 .env 文件已配置。")
    exit(1)

print("openAi开始演示")
print("=" * 50)


openai_model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)

response = openai_model.invoke("你好,OpenAI!请做一个简短的自我介绍。")
print(response.content)
