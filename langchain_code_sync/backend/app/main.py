from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv, find_dotenv
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 导入我们之前定义的逻辑
from core.graph import create_sync_graph
from services.git_manager import PatchManager
from fastapi import BackgroundTasks  # 确保导入了后台任务


# 自动加载 .env 文件 (搜索当前及父级目录)
load_dotenv(find_dotenv())

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


# 正确的定义：取消操作只需要 thread_id
class ThreadRequest(BaseModel):
    thread_id: str


# --- API 接口实现 ---

# 加点注释看一下
# 再加一些注释测试一下呢


@app.post("/sync/start")
async def start_sync(req: SyncRequest, background_tasks: BackgroundTasks):
    config = {"configurable": {"thread_id": req.thread_id}}

    initial_state = {
        "repo_a_dir": req.repo_a_dir,
        "repo_b_dir": req.repo_b_dir,
        "current_commit_index": 0,
        "pending_commits": [],  # 必须清空待处理列表
        "logs": ["任务已进入后台执行队列..."],
        "has_conflict": False,
        "conflicts": [],
        "status": "analyzing",
    }

    # 2. 【核心修复】强制更新状态，将该 thread_id 的进度拨回起点
    sync_graph.update_state(config, initial_state)

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
async def resolve_conflict(req: ResolveRequest, background_tasks: BackgroundTasks):
    config = {"configurable": {"thread_id": req.thread_id}}
    state_snapshot = sync_graph.get_state(config)

    if not state_snapshot.values:
        raise HTTPException(status_code=404, detail="Task not found")

    current_state = state_snapshot.values
    # 实例化 pm
    pm = PatchManager(current_state["repo_a_dir"], current_state["repo_b_dir"])

    try:
        # 1. 物理写入并 git add
        pm.resolve_file_manually(req.file_path, req.content)

        # 2. 如果所有文件都处理完了，推进状态
        if pm.is_all_resolved():
            idx = current_state["current_commit_index"]
            cid = current_state["pending_commits"][idx]

            # 更新元数据文件 (使用 PatchManager 里的方法)
            pm.save_metadata(cid)

            # 获取元数据并提交
            metadata = pm.get_commit_metadata(cid)
            pm.commit_with_metadata(metadata)

            # 手动更新状态机进度
            sync_graph.update_state(
                config,
                {
                    "current_commit_index": idx + 1,
                    "has_conflict": False,
                    "conflicts": [],
                    "status": "applying",
                    "logs": current_state["logs"] + [f"✅ 手动解决并提交: {cid[:8]}"],
                },
            )

            # 【核心修复】使用后台任务唤醒，不阻塞当前 HTTP 请求
            background_tasks.add_task(sync_graph.invoke, None, config)

            return {"status": "resumed"}

        return {"status": "pending"}
    except Exception as e:
        # 在后端打印详细错误，方便我们排查 500 的真相
        import traceback

        print(f"CRITICAL ERROR IN RESOLVE: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync/confirm_push")
async def confirm_push(req: ThreadRequest, background_tasks: BackgroundTasks):
    config = {"configurable": {"thread_id": req.thread_id}}

    state_snapshot = sync_graph.get_state(config)
    if not state_snapshot.values:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 1. 【核心修复】标记一个正在推送的临时状态，避免前端轮询到旧的 awaiting_push
    # 我们把状态改为一个中间态 'pushing'，并添加一条明确的日志
    sync_graph.update_state(
        config,
        {
            "status": "pushing",
            "logs": state_snapshot.values["logs"]
            + ["🔔 用户已确认，准备执行远程推送..."],
        },
    )

    # 2. 唤醒图运行 push_approval 节点
    background_tasks.add_task(sync_graph.invoke, None, config)

    return {"status": "ok"}


@app.post("/sync/cancel")
async def cancel_sync(req: ThreadRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    # 获取当前状态
    state_snapshot = sync_graph.get_state(config)
    if not state_snapshot.values:
        return {"message": "任务已不存在"}

    # 【核心修复】手动将状态拨向结束，这样轮询就不会再拿到 awaiting_push
    sync_graph.update_state(
        config,
        {
            "status": "completed",
            "logs": state_snapshot.values["logs"] + ["🚫 用户取消了本次同步推送。"],
        },
    )

    return {"message": "Sync canceled"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
