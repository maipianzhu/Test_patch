import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';

export interface Conflict {
    file_path: string;
    content: string;
}

export interface MergeWorkstationProps {
    conflict: Conflict;
    onResolve: (filePath: string, content: string) => Promise<void>;
}

const MergeWorkstation: React.FC<MergeWorkstationProps> = ({
    conflict,
    onResolve,
}) => {
    // Determine language from file extension
    const getLanguage = (path: string) => {
        if (path.endsWith('.py')) return 'python';
        if (path.endsWith('.ts') || path.endsWith('.tsx')) return 'typescript';
        if (path.endsWith('.js') || path.endsWith('.jsx')) return 'javascript';
        if (path.endsWith('.json')) return 'json';
        if (path.endsWith('.md')) return 'markdown';
        return 'plaintext';
    };

    const fileName = conflict?.file_path || 'Unknown File';
    const initialContent = conflict?.content || '';
    const language = getLanguage(fileName);

    const [content, setContent] = useState(initialContent);

    // Update content when conflict prop changes
    useEffect(() => {
        setContent(conflict?.content || '');
    }, [conflict]);

    const handleEditorChange = (value: string | undefined) => {
        setContent(value || '');
    };

    const handleSave = () => {
        if (onResolve && conflict) {
            onResolve(conflict.file_path, content);
        }
    };

    const handleCancel = () => {
        // Optional: Reset content or emit cancel event if needed
        setContent(initialContent);
    };

    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            backgroundColor: '#ffffff',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
        }}>
            {/* Header */}
            <div style={{
                padding: '12px 16px',
                backgroundColor: '#f8f9fa',
                borderBottom: '1px solid #e1e4e8',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                zIndex: 10
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '18px' }}>📄</span>
                    <h3 style={{
                        margin: 0,
                        fontSize: '14px',
                        fontWeight: 600,
                        color: '#24292e'
                    }}>
                        {fileName}
                    </h3>
                    <span style={{
                        fontSize: '12px',
                        color: '#586069',
                        backgroundColor: '#e1e4e8',
                        padding: '2px 6px',
                        borderRadius: '12px'
                    }}>
                        {language}
                    </span>
                </div>

                <div style={{ display: 'flex', gap: '10px' }}>
                    <button
                        onClick={handleCancel}
                        style={{
                            padding: '6px 14px',
                            border: '1px solid #d1d5da',
                            borderRadius: '6px',
                            background: 'white',
                            color: '#24292e',
                            fontSize: '13px',
                            fontWeight: 500,
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            boxShadow: '0 1px 0 rgba(27,31,35,0.04)'
                        }}
                        onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
                        onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'white'}
                    >
                        Reset
                    </button>
                    <button
                        onClick={handleSave}
                        style={{
                            padding: '6px 14px',
                            border: '1px solid rgba(27,31,35,0.15)',
                            borderRadius: '6px',
                            background: '#2ea44f',
                            color: 'white',
                            fontSize: '13px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            boxShadow: '0 1px 0 rgba(27,31,35,0.1)'
                        }}
                        onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#2c974b'}
                        onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#2ea44f'}
                    >
                        Resolve & Save
                    </button>
                </div>
            </div>

            {/* Editor Container */}
            <div style={{ flex: 1, position: 'relative' }}>
                <Editor
                    height="100%"
                    defaultLanguage={language}
                    value={content}
                    onChange={handleEditorChange}
                    theme="vs-light"
                    options={{
                        minimap: { enabled: true },
                        fontSize: 13,
                        lineNumbers: 'on',
                        roundedSelection: false,
                        scrollBeyondLastLine: false,
                        readOnly: false,
                        automaticLayout: true,
                        padding: { top: 16 }
                    }}
                />
            </div>
        </div>
    );
};

export default MergeWorkstation;