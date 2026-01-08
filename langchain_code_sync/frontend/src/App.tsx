import React, { useState, useEffect } from 'react';
import { syncApi } from './api';
import MergeWorkstation from './components/MergeWorkstation';
import { Terminal, Play, CheckCircle } from 'lucide-react';

function App() {
    // 生成一个持久的 threadId
    const [threadId] = useState(`user_${Math.random().toString(36).slice(2, 9)}`);
    const [repoA, setRepoA] = useState('');
    const [repoB, setRepoB] = useState('');
    const [state, setState] = useState<any>(null);
    const [isPolling, setIsPolling] = useState(false);

    // --- 关键方法：处理手动合并提交 ---
    const handleResolve = async (filePath: string, content: string) => {
        try {
            // 1. 告诉后端：这个文件修好了
            await syncApi.resolve(threadId, filePath, content);

            // 2. 核心：乐观更新 (Optimistic Update)
            // 即使后端还没轮询回来，我们也立即让前端切回“正在应用”状态
            // 这样用户点击按钮后，界面会立刻变回黑色日志区，体验会很顺滑
            setState((prev: any) => ({
                ...prev,
                status: 'applying',
                has_conflict: false,
                conflicts: []
            }));

            console.log("冲突已提交，等待后端推进...");
        } catch (e) {
            console.error("提交合并失败", e);
            alert("提交合并失败，请检查网络或后端日志");
        }
    };

    // 轮询逻辑：每 2 秒向后端要一次最新状态
    useEffect(() => {
        let timer: number;

        // 核心逻辑：如果是正在应用中，才开启轮询
        // 如果已经是 'conflicted'（冲突中）或 'completed'（已完成），则不需要轮询
        if (isPolling && state?.status !== 'conflicted' && state?.status !== 'completed') {
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
    }, [isPolling, threadId, state?.status]); // 增加 state.status 作为依赖项

    const startSync = async () => {
        // 1. 【核心修复】立即给用户反馈，清空旧的日志和状态
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

            <main className="flex-1 overflow-hidden relative">
                {!state ? (
                    <div className="flex items-center justify-center h-full text-gray-400 font-mono italic">
                        请在上方输入仓库 URL 并点击开始同步
                    </div>
                ) : state.status === 'conflicted' ? (
                    /* 核心冲突处理界面 */
                    <MergeWorkstation
                        conflict={state.conflicts[0]}
                        onResolve={handleResolve} // 调用上面定义的方法
                    />
                ) : (
                    /* 日志展示界面 */
                    <div className="p-6 h-full overflow-y-auto font-mono bg-gray-900 text-green-400">
                        {state.logs.map((log: string, i: number) => (
                            <div key={i} className="mb-1">{`> ${log}`}</div>
                        ))}
                        {state.status === 'applying' && <div className="animate-pulse ml-4 mt-2">_ 正在处理补丁序列...</div>}
                        {state.status === 'completed' && (
                            <div className="text-blue-400 mt-6 flex items-center gap-2 font-bold text-lg">
                                <CheckCircle size={24} /> 所有补丁已成功同步至本地及远程！
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;