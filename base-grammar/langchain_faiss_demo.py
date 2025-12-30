from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

# 1、初始化Embedding模型
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

# 2、准备知识（Document）
docs = [
    Document(
        page_content="苹果是一种红色或绿色的水果,吃起来脆脆的,酸甜可口",
        metadata={"source": "fruit_book"},
    ),
    Document(
        page_content="草莓是一种红色,小小的很脆弱,吃起来很可口",
        metadata={"source": "fruit_book"},
    ),
    Document(
        page_content="特斯拉是一家生产电动汽车的公司,成立于2008年",
        metadata={"source": "tech_book"},
    ),
]

# 3、创建向量数据库
vector_db = FAISS.from_documents(docs, embeddings)

# 4、进行搜索
query = "我想吃脆脆甜甜的水果"

results = vector_db.similarity_search(query, k=1)
for res in results:
    print("-" * 20)
    print(f"找到的内容:{res.page_content}")
    print(f"来源:{res.metadata}")

# 5、保存与加载（FAISS 是内存数据库,重启消息,所以必须保存）
vector_db.save_local("my_faiss_index")
print("索引已经保存到本地了")


# 6、以后重新加载使用
