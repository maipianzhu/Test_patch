import React, { useState, useEffect } from 'react';
import { syncApi } from './api';
import MergeWorkstation from './components/MergeWorkstation'; // 我们之前设计的组件
import { Terminal, Play, CheckCircle, AlertTriangle } from 'lucide-react';

function App() {
    const [threadId] = useState(`user_${Math.random().toString(36).slice(2, 9)}`);
    const [repoA, setRepoA] = useState('');
    const [repoB, setRepoB] = useState('');
    const [state, setState] = useState<any>(null);
    const [isPolling, setIsPolling] = useState(false);

    // 轮询逻辑
    useEffect(() => {
        let timer: number;
        if (isPolling) {
            timer = window.setInterval(async () => {
                try {
                    const res = await syncApi.getStatus(threadId);
                    setState(res.data);
                } catch (e: any) {
                    // 如果是 404，说明后端还没准备好 Checkpoint，忽略它
                    if (e.response?.status === 404) {
                        console.log("等待任务初始化...");
                    } else {
                        console.error("轮询出错", e);
                    }
                }
            }, 2000);
        }
        return () => clearInterval(timer);
    }, [isPolling, threadId]);

    const startSync = async () => {
        setIsPolling(true);
        await syncApi.start(repoA, repoB, threadId);
    };

    return (
        <div className="h-screen flex flex-col bg-gray-50 text-gray-900">
            {/* 导航栏 */}
            <header className="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm">
                <h1 className="text-xl font-bold flex items-center gap-2">
                    <Terminal className="text-blue-600" /> Git Sync Agent
                </h1>
                <div className="flex gap-4">
                    <input
                        className="border p-2 rounded w-64 text-sm"
                        placeholder="Repo A 路径 (源)"
                        value={repoA} onChange={e => setRepoA(e.target.value)}
                    />
                    <input
                        className="border p-2 rounded w-64 text-sm"
                        placeholder="Repo B 路径 (目标)"
                        value={repoB} onChange={e => setRepoB(e.target.value)}
                    />
                    <button
                        onClick={startSync}
                        className="bg-blue-600 text-white px-4 py-2 rounded flex items-center gap-2 hover:bg-blue-700 transition"
                    >
                        <Play size={16} /> 开始同步
                    </button>
                </div>
            </header>

            {/* 主工作区 */}
            <main className="flex-1 overflow-hidden relative">
                {!state ? (
                    <div className="flex items-center justify-center h-full text-gray-400">
                        请输入路径并开始同步
                    </div>
                ) : state.status === 'conflicted' ? (
                    /* 核心冲突处理界面 */
                    <MergeWorkstation
                        conflict={state.conflicts[0]}
                        onResolve={async (path, content) => {
                            await syncApi.resolve(threadId, path, content);
                            // 提交后重置本地状态，等待轮询更新
                            setState({ ...state, status: 'applying' });
                        }}
                    />
                ) : (
                    /* 日志展示界面 */
                    <div className="p-6 h-full overflow-y-auto font-mono bg-gray-900 text-green-400">
                        {state.logs.map((log: string, i: number) => (
                            <div key={i} className="mb-1">{`> ${log}`}</div>
                        ))}
                        {state.status === 'applying' && <div className="animate-pulse">_ 正在处理补丁...</div>}
                        {state.status === 'completed' && (
                            <div className="text-blue-400 mt-4 flex items-center gap-2">
                                <CheckCircle size={20} /> 所有补丁已成功同步！
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;