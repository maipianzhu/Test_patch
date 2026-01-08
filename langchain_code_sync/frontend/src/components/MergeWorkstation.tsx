import React, { useState, useEffect, useRef } from 'react';
import Editor, { Monaco } from '@monaco-editor/react';
import * as diff from 'diff';

// 定义接口，解决 TypeScript 找不到名称的问题
interface ConflictProps {
    conflict: {
        file_path: string;
        base_content: string;
        ours_content: string;
        theirs_content: string;
        ai_suggestion: string | null;
    };
    onResolve: (filePath: string, resolvedContent: string) => void;
}

const MergeWorkstation: React.FC<ConflictProps> = ({ conflict, onResolve }) => {
    const [mergedContent, setMergedContent] = useState("");

    // 使用 Ref 记录三个编辑器的实例，以便统一涂色
    const editorsRef = useRef<{ type: string; editor: any }[]>([]);

    // 当文件切换时，重置中间栏内容并清空编辑器引用记录
    useEffect(() => {
        setMergedContent(conflict.ai_suggestion || conflict.ours_content || "");
        editorsRef.current = [];
    }, [conflict]);

    /**
     * 核心逻辑：精准计算并高亮差异
     */
    const applyHighlighter = (monaco: Monaco) => {
        // 1. 计算 Ours 和 Theirs 分别相对于 Base 的变化
        const oursDiff = diff.diffLines(conflict.base_content, conflict.ours_content);
        const theirsDiff = diff.diffLines(conflict.base_content, conflict.theirs_content);

        // 辅助函数：将 diff 数组转为 Map<行号, 内容>
        const getChangeMap = (diffArray: diff.Change[]) => {
            let currentLine = 1;
            const changeMap = new Map<number, string>();
            diffArray.forEach(part => {
                if (part.added) {
                    const lines = part.value.split('\n');
                    // 去掉最后一个因 split 产生的空行
                    if (lines[lines.length - 1] === "") lines.pop();
                    lines.forEach((text, i) => {
                        changeMap.set(currentLine + i, text.trim());
                    });
                    currentLine += part.count!;
                } else if (!part.removed) {
                    currentLine += part.count!;
                }
            });
            return changeMap;
        };

        const oursChanges = getChangeMap(oursDiff);
        const theirsChanges = getChangeMap(theirsDiff);

        // 2. 遍历编辑器实例进行涂色
        editorsRef.current.forEach(({ type, editor }) => {
            const decorations: any[] = [];
            const isOurs = type === 'ours';
            const isTheirs = type === 'theirs';

            const currentMap = isOurs ? oursChanges : (isTheirs ? theirsChanges : new Map());
            const opponentContent = isOurs ? conflict.theirs_content : conflict.ours_content;

            currentMap.forEach((text, lineNum) => {
                // 精准冲突判定：如果当前行在对方的内容里找不到完全一致的行，则是冲突
                const isTrueConflict = !opponentContent.includes(text);

                let colorClass = "";
                let borderClass = "";
                let rulerColor = "";

                if (isTrueConflict) {
                    colorClass = "bg-red-900/30";
                    borderClass = "border-l-4 border-red-500";
                    rulerColor = "red";
                } else {
                    // 如果两边改得一模一样，使用淡灰色
                    colorClass = "bg-gray-700/20";
                    borderClass = "border-l-2 border-gray-400";
                    rulerColor = "gray";
                }

                // 如果不是冲突但又是本地特有改动，显示蓝/绿
                if (!isTrueConflict) {
                    // 保持低调颜色
                } else if (isOurs) {
                    colorClass = "bg-blue-900/20";
                    borderClass = "border-l-4 border-blue-500";
                    rulerColor = "blue";
                } else if (isTheirs) {
                    colorClass = "bg-green-900/20";
                    borderClass = "border-l-4 border-green-500";
                    rulerColor = "green";
                }

                decorations.push({
                    range: new monaco.Range(lineNum, 1, lineNum, 1),
                    options: {
                        isWholeLine: true,
                        className: colorClass,
                        linesDecorationsClassName: borderClass,
                        overviewRuler: { color: rulerColor, position: 1 }
                    }
                });
            });

            // 应用装饰
            editor.deltaDecorations([], decorations);
        });
    };

    const onEditorMount = (editor: any, monaco: Monaco, type: string) => {
        editorsRef.current.push({ type, editor });
        // 当三个编辑器都挂载完成后，执行高亮
        if (editorsRef.current.length === 3) {
            applyHighlighter(monaco);
        }
    };

    return (
        <div className="flex flex-col w-full h-full bg-[#1e1e1e] overflow-hidden">
            {/* 顶部状态栏 */}
            <div className="flex items-center justify-between px-4 py-2 bg-[#252526] border-b border-[#333]">
                <div className="flex items-center gap-3">
                    <span className="text-blue-400 font-mono text-sm">{conflict.file_path.split('/').pop()}</span>
                    <span className="text-gray-500 text-xs truncate max-w-xs">{conflict.file_path}</span>
                    <div className="flex items-center gap-2 ml-4">
                        <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></span>
                        <span className="text-red-400 text-xs font-bold uppercase tracking-widest">Conflict Detected</span>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setMergedContent(conflict.ours_content)}
                        className="px-3 py-1 text-xs text-gray-400 hover:text-white transition"
                    >
                        重置
                    </button>
                    <button
                        onClick={() => onResolve(conflict.file_path, mergedContent)}
                        className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-1.5 rounded text-sm font-bold shadow-lg transition-all"
                    >
                        确认合并并继续
                    </button>
                </div>
            </div>

            {/* 三栏编辑器主体 */}
            <div className="flex flex-1 w-full" style={{ height: 'calc(100vh - 120px)' }}>

                {/* 左栏：Ours */}
                <div className="flex-1 flex flex-col border-r border-[#333]">
                    <div className="bg-[#2d2d2d] text-blue-300 text-[10px] px-2 py-1 font-bold">本地分支 (OURS)</div>
                    <div className="flex-1">
                        <Editor
                            theme="vs-dark"
                            language="python"
                            value={conflict.ours_content}
                            onMount={(e, m) => onEditorMount(e, m, 'ours')}
                            options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false }}
                        />
                    </div>
                </div>

                {/* 中栏：Result */}
                <div className="flex-1 flex flex-col border-r border-[#444] z-10 shadow-2xl ring-1 ring-white/5">
                    <div className="bg-[#094771] text-white text-[10px] px-2 py-1 font-bold text-center italic">最终合并结果 (RESULT)</div>
                    <div className="flex-1">
                        <Editor
                            theme="vs-dark"
                            language="python"
                            value={mergedContent}
                            onChange={(v) => setMergedContent(v || "")}
                            onMount={(e, m) => onEditorMount(e, m, 'result')}
                            options={{ minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false }}
                        />
                    </div>
                </div>

                {/* 右栏：Theirs */}
                <div className="flex-1 flex flex-col">
                    <div className="bg-[#2d2d2d] text-green-300 text-[10px] px-2 py-1 font-bold text-right">补丁来源 (THEIRS)</div>
                    <div className="flex-1">
                        <Editor
                            theme="vs-dark"
                            language="python"
                            value={conflict.theirs_content}
                            onMount={(e, m) => onEditorMount(e, m, 'theirs')}
                            options={{ readOnly: true, minimap: { enabled: false }, fontSize: 12, scrollBeyondLastLine: false }}
                        />
                    </div>
                </div>

            </div>
        </div>
    );
};

export default MergeWorkstation;