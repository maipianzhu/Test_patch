from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 检查环境变量
if not os.getenv("GOOGLE_API_KEY"):
    print("❌ 错误: 未找到 GOOGLE_API_KEY，请确保 .env 文件已配置。")
    exit(1)

print("✅ 环境加载成功，开始 LangChain Google 使用演示...\n")
print("=" * 50)

gg_model = ChatGoogleGenerativeAI(
    model="gemini-exp-1206",
    temperature=0.7,
)
""" 
AIzaSyA-1234567890abcdefghijklmnopqrstuv
AIzaSyBvbBsUNYd90GG2HV-73ETg-RDmdUx4V_o
AIzaSyB0jAipA0NLnAmwgxjeQ6eJpYzwLOGGRtc
AIzaSyDCB79a0GA7fqZEXtt4d8hij6A316ulyl4
AIzaSyBPmZs0wk0rnUMYLAbu3Owlu3alK2UGopc
AIzaSyAXkx3934Zo-JYslaMeIBwqGIjw3q1Whcs


"""
response = gg_model.invoke("你好,Google!请做一个简短的自我介绍。")
print(response.content)
