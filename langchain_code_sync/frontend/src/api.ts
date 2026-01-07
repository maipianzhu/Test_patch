import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export const syncApi = {
    // 开始同步
    start: (repoA: string, repoB: string, threadId: string) =>
        axios.post(`${API_BASE}/sync/start`, { repo_a_dir: repoA, repo_b_dir: repoB, thread_id: threadId }),

    // 获取当前状态（轮询用）
    getStatus: (threadId: string) =>
        axios.get(`${API_BASE}/sync/status?thread_id=${threadId}`),

    // 提交人工合并结果
    resolve: (threadId: string, filePath: string, content: string) =>
        axios.post(`${API_BASE}/sync/resolve`, { thread_id: threadId, file_path: filePath, content: content })
};