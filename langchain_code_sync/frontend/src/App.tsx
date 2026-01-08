import React, { useState, useEffect } from 'react';
import { syncApi } from './api';
import MergeWorkstation from './components/MergeWorkstation';
import { Terminal, Play, CheckCircle, AlertTriangle, Rocket, XCircle } from 'lucide-react';

function App() {
    // 生成一个持久的 threadId
    const [threadId] = useState(`user_${Math.random().toString(36).slice(2, 9)}`);
    const [repoA, setRepoA] = useState('');
    const [repoB, setRepoB] = useState('');
    const [state, setState] = useState<any>(null);
    const [isPolling, setIsPolling] = useState(false);

    // --- 1. 处理代码冲突合并提交 ---
    const handleResolve = async (filePath: string, content: string) => {
        try {
            await syncApi.resolve(threadId, filePath, content);
            // 乐观更新：立即切回日志界面
            setState((prev: any) => ({
                ...prev,
                status: 'applying',
                has_conflict: false,
                conflicts: []
            }));
        } catch (e) {
            console.error("提交合并失败", e);
            alert("提交合并失败，请检查网络或后端日志");
        }
    };

    // --- 2. 新增：处理最终推送确认 ---
    const handleConfirmPush = async () => {
        try {
            // 乐观更新状态
            setState((prev: any) => ({ ...prev, status: 'applying' }));
            // 调用后端确认推送接口
            await syncApi.confirmPush(threadId);
        } catch (e) {
            console.error("推送失败", e);
            alert("推送指令发送失败");
        }
    };

    // 轮询逻辑：每 2 秒获取一次状态
    useEffect(() => {
        let timer: number;

        // 核心修改：在 'conflicted'、'awaiting_push' 或 'completed' 状态下停止轮询，等待人工操作
        const shouldStopPolling =
            state?.status === 'conflicted' ||
            state?.status === 'awaiting_push' ||
            state?.status === 'completed' ||
            state?.status === 'error';

        if (isPolling && !shouldStopPolling) {
            timer = window.setInterval(async () => {
                try {
                    const res = await syncApi.getStatus(threadId);
                    setState(res.data);
                } catch (e: any) {
                    console.error("轮询失败", e);
                }
            }, 2000);
        }

        return () => clearInterval(timer);
    }, [isPolling, threadId, state?.status]);

    const startSync = async () => {
        setState(null);
        setIsPolling(true);
        try {
            await syncApi.start(repoA, repoB, threadId);
        } catch (e) {
            console.error("启动失败", e);
            alert("启动失败，请检查后端");
            setIsPolling(false);
        }
    };

    const handleCancel = async () => {
        setIsPolling(false); // 先停掉轮询
        await syncApi.cancelSync(threadId); // 告诉后端任务结束了
        setState(null); // 清空 UI
    };

    return (
        <div className="h-screen flex flex-col bg-gray-50 text-gray-900">
            <header className="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm">
                <h1 className="text-xl font-bold flex items-center gap-2">
                    <Terminal className="text-blue-600" /> Git Sync Agent
                </h1>
                <div className="flex gap-4">
                    <input className="border p-2 rounded w-64 text-sm" placeholder="Repo A (源)" value={repoA} onChange={e => setRepoA(e.target.value)} />
                    <input className="border p-2 rounded w-64 text-sm" placeholder="Repo B (目标)" value={repoB} onChange={e => setRepoB(e.target.value)} />
                    <button onClick={startSync} className="bg-blue-600 text-white px-4 py-2 rounded flex items-center gap-2 hover:bg-blue-700 transition">
                        <Play size={16} /> 开始同步
                    </button>
                </div>
            </header>

            <main className="flex-1 overflow-hidden relative flex flex-col">
                {!state ? (
                    <div className="flex items-center justify-center h-full text-gray-400 font-mono italic">
                        请在上方输入仓库 URL 并点击开始同步
                    </div>
                ) : state.status === 'conflicted' ? (
                    <MergeWorkstation conflict={state.conflicts[0]} onResolve={handleResolve} />
                ) : state.status === 'awaiting_push' ? (
                    /* --- 核心新增：推送确认界面 --- */
                    <div className="flex-1 flex items-center justify-center bg-gray-100 p-6">
                        <div className="bg-white p-8 rounded-xl shadow-2xl max-w-2xl w-full border border-orange-200">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-orange-100 rounded-full text-orange-600">
                                    <AlertTriangle size={28} />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-gray-800">同步预检确认</h2>
                                    <p className="text-sm text-gray-500">所有补丁已在本地应用成功，请确认是否推送到远程仓库。</p>
                                </div>
                            </div>

                            <div className="mb-6">
                                <label className="block text-xs font-bold text-gray-400 uppercase mb-2">待推送的提交摘要：</label>
                                <pre className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-xs max-h-60 overflow-y-auto shadow-inner">
                                    {state.push_summary || "暂无提交明细"}
                                </pre>
                            </div>

                            <div className="flex justify-end gap-4">
                                <button
                                    onClick={handleCancel}
                                    className="px-6 py-2 text-gray-500 hover:bg-gray-100 rounded-lg transition"
                                >
                                    放弃本次同步
                                </button>
                                <button
                                    onClick={handleConfirmPush}
                                    className="bg-orange-600 text-white px-10 py-2 rounded-lg font-bold hover:bg-orange-700 shadow-lg flex items-center gap-2 transition-all transform hover:scale-105"
                                >
                                    <Rocket size={18} /> 确认推送并完成
                                </button>
                            </div>
                        </div>
                    </div>
                ) : (
                    /* 日志展示界面 */
                    <div className="p-6 h-full overflow-y-auto font-mono bg-gray-900 text-green-400">
                        {state.logs.map((log: string, i: number) => (
                            <div key={i} className="mb-1 leading-relaxed">{`> ${log}`}</div>
                        ))}
                        {(state.status === 'applying' || state.status === 'pushing') && (
                            <div className="animate-pulse ml-4 mt-2">
                                _ {state.status === 'pushing' ? '正在推送到远程仓库...' : '正在处理任务序列...'}
                            </div>
                        )}
                        {state.status === 'completed' && (
                            <div className="text-blue-400 mt-6 p-4 border border-blue-900/50 bg-blue-900/20 rounded flex items-center gap-3 font-bold text-lg">
                                <CheckCircle size={24} /> 所有操作已圆满完成！
                            </div>
                        )}
                        {state.status === 'error' && (
                            <div className="text-red-400 mt-6 p-4 border border-red-900/50 bg-red-900/20 rounded flex items-center gap-3 font-bold">
                                <XCircle size={24} /> 任务中断：请检查日志输出
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;