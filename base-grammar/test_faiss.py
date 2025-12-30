import numpy as np
import faiss

# 准备数据
dimension = 4

db_vectors = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],  # 向量A
        [0.0, 1.0, 0.0, 0.0],  # 向量B
        [0.9, 0.0, 1.0, 0.0],  # 向量C
        [0.0, 0.0, 0.0, 1.0],  # 向量D
    ]
).astype("float32")

# 创建索引
index = faiss.IndexFlatL2(dimension)

# 向量装入索引
index.add(db_vectors)
print(f"索引中现在的向量数量:{index.ntotal}")

# 模拟搜索
query_vector = np.array([[1.0, 0.0, 0.0, 0.0]]).astype("float32")  # 模拟用户输入的向量

# 搜索最相似的两个结果
topK = 2
distances, indices = index.search(query_vector, topK)

# 查看结果
print("搜索结果如下:")
print(f"最相似的向量索引:{indices}")
print(f"他们与查询向量的距离距离:{distances}")
