# Plan: cockpit-v0302-files — Cockpit v0.30.2 文件浏览器 + 看板集成

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

Cockpit 由两个独立的服务构成：`ccc-chat-server.py`（Execute 模式所在）和 `ccc-cockpit.py`（Dashboard）。当前均无文件树支持。

- **入口/核心文件**：
  - `scripts/ccc-chat-server.py`（1260 行）— FastAPI 应用，含 Chat/Execute/Board 三模式，HTML 模板 + CSS + JS 全内联于 `HTML_UI` 变量（494-1240 行）
  - `scripts/ccc-cockpit.py`（559 行）— HTTP 服务器，Dashboard 展示机器/端口/项目状态，HTML 内联渲染

- **当前结构要点**：
  - Execute 模式（`ccc-chat-server.py:241-388`）：接受用户指令 → 运行 `claude -p` 子进程 → SSE 流式返回文本 + tool_use 事件
  - Execute 模式的 HTML 面板（`ccc-chat-server.py:754-764`）：仅包含输入框 `#exec-input` 和消息列表 `#exec-messages`，**零文件树支持**
  - Board 模式已在 Chat Server 中实现（`ccc-chat-server.py:766-774`），代理到 `:7777/api/board`
  - Cockpit Dashboard（`ccc-cockpit.py:464-538`）已处理 `/`、`/api/alive`、`/api/kb/search` 三个路由
  - Cockpit Dashboard 的快速跳转区（`ccc-cockpit.py:342-349`）已有通往 board-server 的链接，但**无内嵌看板数据**

- **待改动点**：
  - `ccc-chat-server.py`：
    - 新增 `GET /api/projects/{id}/files` 路由（返回项目文件树 JSON）
    - `HTML_UI` 中 Execute 面板新增文件树侧栏区域 + CSS + JS 交互
    - 文件树取数逻辑：用 `os.walk` 遍历项目目录，限深度 4，排除 `.git`/`node_modules`/`__pycache__`/`.venv`
  - `ccc-cockpit.py`：
    - 新增 `GET /api/board` 路由 — 请求 `:7777/api/dashboard` 获取各 workspace 的任务列计数
    - Dashboard HTML 新增「看板概览」区域，展示各列任务数

---

## 范围

- **目标**：在 Cockpit Execute 模式中嵌入项目文件树；在 Dashboard 中嵌入看板列统计数据
- **只改文件**：
  - `scripts/ccc-chat-server.py`（Phase 1 + 2）
  - `scripts/ccc-cockpit.py`（Phase 3）
- **不改文件**：
  - `.ccc/infrastructure.md`、`.ccc/state.md`、`.ccc/profile.md`
  - `scripts/ccc-board.py`、`scripts/ccc-board-server.py`
  - 其他任何脚本或测试文件
- **执行方式**：`manual`
- **Phase 数**：3

---

## Phase 1：文件浏览器 — Backend API

### 做什么
为项目文件浏览器提供后端 API `/api/projects/{id}/files`。前端通过此接口获取项目文件树，实现对文件结构的两级（目录/文件）浏览。

### 怎么做

**新增 `GET /api/projects/{id}/files` 路由**（`ccc-chat-server.py`，在 `/api/projects` 路由定义之后，约第 449 行附近）：

- 接收路径参数 `id`（与 `PROJECTS` 字典 key 对应）
- 从 `PROJECTS` 字典获取项目根路径
- 用 `os.walk` 遍历项目目录：
  - 最大递归深度 4（以项目根为 depth=0）
  - 排除目录：`.git`、`node_modules`、`__pycache__`、`.venv`、`.ccc`（匹配任意层级）
  - 排除文件类型：`.pyc`、`.DS_Store`、`*.egg-info/*`
- 返回 JSON 结构：

```json
{
  "project_id": "ccc",
  "root": "/Users/apple/program/CCC",
  "entries": [
    {"name": "scripts", "type": "dir", "path": "scripts", "depth": 1},
    {"name": "ccc-cockpit.py", "type": "file", "path": "scripts/ccc-cockpit.py", "depth": 2, "size": 22593}
  ]
}
```

- 所有 `entries` 为**扁平列表**（非嵌套树），前端按 `path` 中的 `/` 分段渲染
- 每个条目记录 `depth`（从项目根为 0，逐级递增）
- 仅返回**一级足够浏览的粒度**（depth ≤ 4），超大项目通过排除规则控制返回量
- 设置 `max_entries = 500` 截断保护
- 设置 5 秒超时保护（遍历锁定）

**关键函数签名建议**：
```python
def get_project_files(project_id: str) -> dict:
    """遍历项目目录，返回扁平文件列表。"""
```

### 验收清单

- [ ] `GET /api/projects/ccc/files` 返回 200 + 正确 JSON 结构
- [ ] 返回的 `entries` 包含目录和文件，各条目含 `name/type/path/depth` 字段
- [ ] `.git`、`node_modules` 等排除目录不出现
- [ ] 不存在的 project id 返回 404
- [ ] 超大项目被 max_entries 500 截断，不 OOM
- [ ] 遍历超时 5s 保护

### 验收

- [返回结构正确]（参考：`curl -sS -u ccc:claude2026 http://localhost:8084/api/projects/ccc/files | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['entries']), 'entries')"`）
- [排除目录可见]（参考：结果中无 `.git`/`node_modules` 路径）
- [大项目截断]（参考：`curl -sS -u ccc:claude2026 http://localhost:8084/api/projects/ccc/files | python3 -c "import sys,json; d=json.load(sys.stdin); print('truncated' if d.get('truncated') else 'full')"`）

---

## Phase 2：文件浏览器 — Frontend UI

### 做什么
在 Execute 模式的面板中增加可折叠的项目文件树侧栏。用户可浏览项目目录结构、点击文件查看代码内容（只读），与当前 Execute 输入区域共存。

### 怎么做

**CSS 新增**（`ccc-chat-server.py` HTML_UI 的 `<style>` 块，约第 502-731 行之间，在 `#board-panel` 等现有样式后追加）：

- `.exec-layout { display:flex; flex:1; overflow:hidden; }` — 将 Execute 面板改为左右分栏（主消息区 + 文件侧栏）
- `.file-tree-panel { width:260px; flex-shrink:0; border-right:1px solid var(--border); overflow-y:auto; background:var(--surface); }` — 左侧固定 260px
- `.exec-main { flex:1; display:flex; flex-direction:column; overflow:hidden; }` — 右侧占满剩余空间
- `.file-item { padding:4px 12px; font-size:12px; cursor:pointer; display:flex; align-items:center; gap:4px; }` — 文件节点
- `.file-item:hover { background:var(--code-bg); }` — 悬停高亮
- `.file-item.dir { font-weight:500; }` — 目录粗体
- `.file-item .icon { width:16px; text-align:center; flex-shrink:0; }` — 图标
- `.file-item .name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }` — 文件名
- `.file-tree-panel .header { padding:8px 12px; font-size:12px; font-weight:600; color:var(--text-secondary); border-bottom:1px solid var(--border); }` — 面板头
- `.file-content-preview { max-height:400px; overflow-y:auto; background:var(--code-bg); border-radius:8px; padding:12px; margin:8px 0; font-size:12px; white-space:pre-wrap; }` — 文件预览区

**Execute 面板 HTML 结构调整**（约第 754 行 `<div id="exec-panel">`）：

- 当前结构：
```html
<div id="exec-panel" class="tab-panel">
  <div id="exec-messages"></div>
  <div id="input-area">...</div>
</div>
```
- 改为：
```html
<div id="exec-panel" class="tab-panel">
  <div class="exec-layout">
    <div class="file-tree-panel">
      <div class="header">文件</div>
      <div id="file-tree"></div>
    </div>
    <div class="exec-main">
      <div id="exec-messages"></div>
      <div id="input-area">...</div>
    </div>
  </div>
</div>
```

**JS 新增**（`<script>` 块内，约第 870 行 `loadProjects()` 之后）：

- `async function loadFileTree()`:
  - 取当前 `currentProject` → `fetch('/api/projects/' + currentProject + '/files')`
  - 调用 `renderFileTree(data.entries)` 渲染到 `#file-tree`
- `function renderFileTree(entries)`:
  - 按 `path` 的 `/` 分段，构建嵌套结构（或直接用扁平列表按 depth 增加缩进 `padding-left: depth * 16px`）
  - 目录项：` name`，点击折叠/展开其子级
  - 文件项：` name`，点击 `fetch('/api/projects/' + project + '/file?path=' + path)` 读取文件内容并显示在消息区
  - `max 300` 条目渲染限制
- `async function readFile(path)`:
  - 新增 `GET /api/projects/{id}/file?path={path}` 路由（Phase 1 未定义？需在 Phase 2 一并新建，或基于文件系统直接返回内容）
  - 文件内容以纯文本形式返回，渲染为 `file-content-preview` 区

**注意**：需要新增 `/api/projects/{id}/file` 路由（含在 Phase 2 后端部分，读取文件内容并返回，支持 `Accept: application/json` 或 `text/plain`）。

**文件内容 API 要求**：
- `GET /api/projects/{id}/file?path=scripts/ccc-cockpit.py`
- 路径安全检查：禁止 `..` 穿越、禁止读取 `.git/`、`node_modules/` 下的文件
- 文件大小限制：≤ 100KB
- 二进制文件检测：扩展名 `.png`/`.jpg`/`.ico`/`.pyc` 等跳过，返回 `{"error": "binary file"}`

**Execute 面板切换项目时自动刷新文件树**：
- 在 `onProjectChange()` 中，若 `currentTab === 'execute'` 则调用 `loadFileTree()`
- 在 `switchTab('execute')` 中调用 `loadFileTree()`

### 验收清单

- [ ] Execute 面板左侧显示文件树，右侧为消息和输入区
- [ ] 目录可折叠/展开，展开后显示子条目
- [ ] 文件名前有 ``/`` 图标
- [ ] 点击文件后，文件内容在消息区以代码块展示
- [ ] 切换项目后文件树自动刷新
- [ ] 文件路径穿越攻击被拦截（`../` 返回 400）
- [ ] `.git` 目录不可见
- [ ] 二进制文件不读取内容
- [ ] 大文件（>100KB）被截断

### 验收

- [文件树展示]（参考：打开 Cockpit Execute 面板，观察左侧文件树区域）
- [目录折叠]（参考：点击目录名，观察子条目显示/隐藏）
- [文件查看]（参考：点击一个 Python 文件，消息区显示语法高亮代码）
- [路径穿越防御]（参考：`curl -sS -u ccc:claude2026 "http://localhost:8084/api/projects/ccc/file?path=../etc/passwd"` 返回 400）

---

## Phase 3：看板集成 — Cockpit Dashboard

### 做什么
在 Cockpit Dashboard（`ccc-cockpit.py`）中新增「看板概览」区域，从 board-server `:7777` 拉取各 workspace 的任务列计数，直接展示在 Dashboard 页面，使用户无需跳转即可概览各项目的看板状态。

### 怎么做

**新增 `GET /api/board` 路由**（`ccc-cockpit.py`，`do_GET()` 方法中，约第 538 行之前）：

- 向 `http://127.0.0.1:7777/api/dashboard?workspace=CCC` 发起 HTTP GET 请求
- 若 board-server 不可用 → 返回 `{"error": "board server unavailable"}`
- 若成功 → 提取 `kpi` 中的 `in_progress`、`abnormal`、`ready_to_release`、`today.released`、`today.fixed` 字段
- 同时请求 `http://127.0.0.1:7777/api/board?workspace=CCC` 获取各列详细任务数（含列名）
- 返回简化的 JSON：

```json
{
  "columns": {
    "backlog": 5,
    "planned": 3,
    "in_progress": 1,
    "testing": 0,
    "verified": 2,
    "released": 8,
    "abnormal": 1
  },
  "kpi": {
    "in_progress": 1,
    "abnormal": 1,
    "ready_to_release": 2,
    "today_released": 3,
    "today_fixed": 1
  },
  "workspaces": {"CCC": "/path", "qxo": "/path"},
  "last_updated": "12:34"
}
```

- 3 秒超时保护
- 缓存：同请求 5 秒内返回旧数据（采用 Cockpit 已有的全局 dict 或直接无缓存，每次重新请求）

**Dashboard 新增「看板概览」HTML 区域**（`render_html()` 中，约第 360 行「端口 & 服务」区之后，「项目」区之前）：

- 新增 `<div class="sec-title">看板概览</div>`
- 可选的列计数卡片网格：每个列显示名称 + 任务数 + 颜色徽标
- 颜色映射：backlog=灰、planned=蓝、in_progress=黄、testing=紫、verified=绿、released=深绿、abnormal=红
- 每列为一个压缩卡片（`card` 样式），紧凑布局
- 卡片显示列名和计数，计数为 0 时显示灰色
- 若 board-server 离线 → 显示「看板服务离线」（灰色文字）
- KPI 摘要行：处理中(N)、异常(N)、待发布(N)、今日发布(N)

**JS 加载（内联 `<script>` 块内，现有 JS 后追加）」**：
- `function loadBoardData()`：
  - `fetch('/api/board')` → 解析 JSON
  - 渲染列卡片网格
  - 渲染 KPI 行
  - 失败时显示离线状态
- 页面刷新时调用（已有全页刷新机制，无需轮询）
- 或者在现有页面加载时集成（`render_html()` 服务端渲染）

**服务端渲染方案（推荐，无需 JS 轮询）**：
- 在 `build_cockpit_data()` 中新增 board 数据拉取：
  - 并行请求 `:7777/api/board` 和 `:7777/api/dashboard`
  - 结果写入 `data["board"]`
  - 超时/离线 → `data["board"] = None`
- 在 `render_html()` 中：
  - 若 `data.get("board")` 存在 → 渲染列卡片网格
  - 否则渲染「看板服务离线」

**更新时间标注**：在看板区域底部显示「数据更新时间：HH:MM」

### 验收清单

- [ ] Dashboard 中出现「看板概览」区域
- [ ] 7 列各显示名称和任务计数（backlog → released + abnormal）
- [ ] 计数为 0 的列显示为灰色
- [ ] KPI 摘要行（处理中/异常/待发布/今日发布）
- [ ] board-server 离线时显示「看板服务离线」
- [ ] 页面整体加载不受 board-server 离线影响（5s 超时后显示离线）
- [ ] 无 JS 依赖（服务端渲染）

### 验收

- [看板区域]（参考：重启 Cockpit 后打开 `http://localhost:7778`，观察「看板概览」区域）
- [列计数正确]（参考：与 board-server 的 Board 页面数据对比）
- [离线容错]（参考：停 `:7777` 后刷新 Dashboard，看板区域显示离线，其他区域正常）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | Phase 1 — 文件浏览器后端 API | `feat(cockpit): 文件浏览器后端 API — 项目文件树接口 (phase 1/3)` |
| 2 | Phase 2 — 文件浏览器前端 UI | `feat(cockpit): 文件浏览器前端 UI — Execute 面板文件树 (phase 2/3)` |
| 3 | Phase 3 — 看板集成 | `feat(cockpit): 看板集成 — Dashboard 嵌入列计数 (phase 3/3)` |

规则：每个 phase 一个独立 commit，message 含 phase 编号。

---

## 全局验收清单

- [ ] Python 语法检查通过（参考：`python3 -m py_compile scripts/ccc-chat-server.py && python3 -m py_compile scripts/ccc-cockpit.py`）
- [ ] 重启 Chat Server + Cockpit 后页面正常展示
- [ ] diff 范围仅限 `scripts/ccc-chat-server.py` 和 `scripts/ccc-cockpit.py`
- [ ] 每个 phase 对应一个独立 commit
- [ ] phases.json 与 plan phase 数一致（3 个）
- [ ] Plan 中所有验收意图全部达成
- [ ] Phase 1+2 与 Phase 3 互不依赖；可独立回退

---

## 后续步骤

P1-P3 完成后，Cockpit 从「纯仪表盘 + 纯文本框 Execute」进化为「带文件上下文浏览的 Execute + 看板概览 Dashboard」。后续方向：

| 方向 | 说明 | 优先级 |
|------|------|--------|
| P4: 文件编辑 | 文件树中右键/双击直接编辑保存 | 低 |
| P5: 终端体验 (v0.30.3) | Execute 模式改为实时终端输出，显示 diff | 中 |
| P6: 多 CLI 引擎 (v0.30.4) | 可切换 claude -p / opencode / cursor CLI | 中 |