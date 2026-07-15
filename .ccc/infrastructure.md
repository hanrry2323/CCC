# CCC Infrastructure — 机器 / 端口 / 服务总览

> 本文档是 CCC 基础设施的权威来源。Claude Code 启动时强制读取。
> 变更端口或添加项目后同步更新本文件。

---

## 机器清单

| 主机 | IP | 角色 | OS | 说明 |
|------|-----|------|-----|------|
| M1 | 192.168.3.140 | 开发机 | macOS | 编码、CCC 跑、轻量服务 |
| Mac 2017 | 192.168.3.116 | 编译站 | macOS | Rust 编译、批量任务 |
| feiniu | 192.168.3.131 | 生产机 | Ubuntu | HP 服务、medio-0 部署、ollama |

---

## M1 (192.168.3.140) — 服务端口

| 端口 | 服务 | 说明 |
|------|------|------|
| 4000 | 中转站 Anthropic | flash tier：minimax → opencode |
| 4002 | 中转站 OpenAI | code tier：xfyun → 智谱 |
| 5432 | PostgreSQL | 仅 localhost |
| 7777 | CCC Board Server | 看板 API + UI |
| 7778 | CCC Cockpit | **总控台** |
| 8080 | HP Proxy | 知识库代理 |
| 8082 | HP Memory Store | 向量/记忆 |
| 8083 | HP Bridge | 知识库桥接 |
| 8084 | CCC Chat Server | 移动端聊天/执行/看板 |
| 8095 | qb Dashboard API | FastAPI 后端 |
| 8096 | qb Dashboard Frontend | Vue 3 前端 |

---

## Mac 2017 (192.168.3.116) — 编译站

| 资源 | 路径/端口 | 说明 |
|------|-----------|------|
| Rust | 1.97.0 | cargo check/build |
| Node | 22 | 前端构建 |
| medio-0 源码 | ~/program/Medio-0/ | rsync 自 M1 |
| 编译产物 | target/release/medio-server | 9.5MB |

---

## feiniu (192.168.3.131) — 生产机

| 端口 | 服务 | 说明 |
|------|------|------|
| 3000 | medio-0 Web | 本地媒体中心，已部署 v0.4.0 |
| 11434 | ollama bge-m3 | 向量模型（CPU 模式）|
| 18080 | Money Printer Turbo | xianyu 视频生成 |

### 部署路径

| 项目 | 路径 |
|------|------|
| medio-0 | `/data/projects/medio-0/` |
| HP | 系统服务 |

---

## 各项目端口汇总

| 项目 | 开发端口 | 测试端口 | 生产端口 | 页面 |
|------|----------|----------|----------|------|
| CCC | 7777(看板) / 7778(总控) / 8084(聊天) | — | — | localhost:7778 |
| qb | 8095(API) / 8096(前端) | — | — | localhost:8096 |
| medio-0 | — | — | 192.168.3.131:3000 | feiniu:3000 |
| qx/clawmed | — | — | — | — |
| xianyu | — | — | — | — |
| ai-loop-router | 4000/4002 | — | — | localhost:4000/dashboard |

---

## 项目状态

| 项目 | 版本 | 状态 | 说明 |
|------|------|------|------|
| CCC | v0.28.1 | 运行中 | 框架本体 |
| qb | v0.3.0 | 运行中 | 量化交易，M1 |
| qx/clawmed | v2.1.0 | 开发中 | 医药 AI 决策 |
| medio-0 | v0.4.0 | 已部署 HP | 媒体中心 |
| xianyu | v1.0.0 | 工程化就绪 | 等待开发 |
| ai-loop-router | v3.6.0 | 已排除 CCC | 不动 |

---

## 进程守护（launchd / pm2）

| 服务 | 管理方式 | 状态 |
|------|----------|------|
| CCC Engine | launchd com.ccc.engine | 运行中 |
| CCC Board Server | launchd / pm2 | 运行中 |
| 中转站 | 直接进程 | 运行中 |
| HP 服务 (3个) | 直接进程 | 运行中 |
| qb (5个plist) | launchd | 运行中 |

## CCC Chat Server v2（2026-07-15）

### 架构

```
scripts/ccc-chat-server.py          # 入口 (uvicorn.run)
scripts/chat_server/                # 模块化包
├── config.py                       # Pydantic 配置
├── models.py                       # 数据模型
├── auth.py                         # Basic Auth
├── app.py                          # FastAPI 工厂
├── routers/                        # 路由层
│   ├── chat.py                     # POST /api/chat SSE
│   ├── sessions.py                 # GET/DEL /api/history
│   ├── files.py                    # 文件浏览
│   ├── board.py                    # Board 代理
│   └── projects.py                 # 项目列表
├── services/                       # 服务层
│   ├── claude_client.py            # Claude 子进程 SSE
│   ├── session_store.py            # 会话持久化
│   └── board_client.py             # Board HTTP 客户端
└── frontend/                       # 纯前端 SPA
    ├── index.html
    ├── css/ (variables, base, themes, components)
    └── js/ (state, api, markdown, app + 5 components)
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/chat` | SSE 流式聊天 |
| POST | `/api/execute` | 执行模式 |
| GET | `/api/history` | 会话列表 |
| GET | `/api/history/{id}` | 单个会话 |
| DELETE | `/api/history/{id}` | 删除会话 |
| GET | `/api/projects/{id}/files` | 文件树 |
| GET | `/api/projects/{id}/file` | 文件内容 |
| GET | `/api/board/proxy/*` | Board 代理 |
| POST | `/api/board/proxy/*` | Board 代理 |

