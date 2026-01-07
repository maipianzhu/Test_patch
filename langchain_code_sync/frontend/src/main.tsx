import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css' // 如果你有 css 文件的话，没有就删掉这行

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>,
)