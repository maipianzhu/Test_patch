from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv, find_dotenv

# 自动加载 .env 文件 (搜索当前及父级目录)
load_dotenv(find_dotenv())

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# 导入我们之前定义的逻辑
from core.graph import create_sync_graph
from services.git_manager import PatchManager

app = FastAPI(title="Git Sync Agent API")

# 1. 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 初始化全局单例图对象
# 注意：在生产环境下，这些配置可能从配置文件读取
sync_graph = create_sync_graph()


# --- 请求模型定义 ---
class SyncRequest(BaseModel):
    repo_a_dir: str
    repo_b_dir: str
    thread_id: str  # 每个同步任务的唯一标识


class ResolveRequest(BaseModel):
    thread_id: str
    file_path: str
    content: str  # 用户在 UI 上修好的最终代码


# --- API 接口实现 ---


from fastapi import BackgroundTasks  # 导入后台任务


@app.post("/sync/start")
async def start_sync(req: SyncRequest, background_tasks: BackgroundTasks):
    config = {"configurable": {"thread_id": req.thread_id}}

    initial_state = {
        "repo_a_dir": req.repo_a_dir,
        "repo_b_dir": req.repo_b_dir,
        "current_commit_index": 0,
        "logs": ["任务已进入后台执行队列..."],
        "has_conflict": False,
        "conflicts": [],
        "status": "analyzing",
    }

    # 定义一个后台运行的函数
    def run_workflow():
        try:
            sync_graph.invoke(initial_state, config)
        except Exception as e:
            print(f"Workflow Error: {e}")

    # 将任务丢进后台，立即返回 HTTP 200
    background_tasks.add_task(run_workflow)

    return {"message": "Sync started in background"}


@app.get("/sync/status")
async def get_status(thread_id: str):
    """
    获取任务当前状态（包括日志和冲突详情）
    """
    config = {"configurable": {"thread_id": thread_id}}
    state = sync_graph.get_state(config)

    if not state.values:
        raise HTTPException(status_code=404, detail="任务不存在")

    return state.values


@app.post("/sync/resolve")
async def resolve_conflict(req: ResolveRequest):
    """
    用户提交手动合并的结果，并恢复执行
    """
    config = {"configurable": {"thread_id": req.thread_id}}

    # 1. 获取当前状态以获取仓库路径
    current_state = sync_graph.get_state(config).values
    pm = PatchManager(current_state["repo_a_dir"], current_state["repo_b_dir"])

    # 2. 将修好的代码写入物理文件并执行 git add
    pm.resolve_file_manually(req.file_path, req.content)

    # 3. 如果所有冲突文件都修好了，恢复图的运行
    if pm.is_all_resolved():
        # 传入 None 表示从上次中断的 human_review 节点直接继续
        sync_graph.invoke(None, config)
        return {"status": "resumed", "message": "冲突已解决，流水线继续"}

    return {"status": "pending", "message": "文件已保存，等待其他冲突解决"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
