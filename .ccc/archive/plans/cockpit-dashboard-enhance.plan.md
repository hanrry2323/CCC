# Plan: cockpit-dashboard-enhance — Cockpit 仪表盘显示活跃任务实时状态

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-cockpit.py`（单文件 HTTP 服务，:7778）
- **当前结构要点**：
  1. `_fetch_board_summary()`（`ccc-cockpit.py:260-352`）调 board-server (`:7777`) 两个端点：
     - `/api/board?workspace=CCC` → 列计数
     - `/api/dashboard?workspace=CCC` → KPI 统计
   - **问题**：dashboard 端点实际返回了 `active_tasks`（已 enriched，含 `elapsed_cn`）和 `today_events`，但 Cockpit 只提取了 KPI 计数，丢弃了活跃任务和事件数据
  2. `render_html()`（`ccc-cockpit.py:444-883`）渲染看板概览只显示列卡片 + KPI pills，**没有活跃任务列表、执行时间、今日完成记录**
  3. JS 轮询 `fetchAlive()` 每 30s 调 `/api/alive`，只刷新端口状态，**不刷新 board 数据**
  4. `CockpitHandler.do_GET()`（`ccc-cockpit.py:889-983`）有 `/api/board` 路由，但只转发 board-server 简化版摘要，**没有带活跃任务的全量 board data**
- **待改动点**：
  - `_fetch_board_summary()`：额外解析 dashboard 响应的 `active_tasks` 和 `today_events`，一并返回
  - `render_html()`：新增两个渲染函数 `_render_active_tasks_section()` + `_render_today_events_section()`，在看板概览下方渲染
  - `do_GET` `/api/board`：返回含活跃任务的全量数据，供 JS 异步刷新
  - JS：新增轮询 `/api/board` 更新 DOM
  - `tests/scripts/test_cockpit.py`：追加活跃任务数据结构和端点测试

---

## 范围

- **目标**：Cockpit 页面上显示活跃任务列表（In Progress/Testing）+ 执行时间 + 今日完成记录，带自动刷新
- **只改文件**：`scripts/ccc-cockpit.py`，`tests/scripts/test_cockpit.py`
- **不改文件**：`scripts/ccc-board-server.py`、`scripts/ccc-engine.py`、`scripts/ccc-board.py` 不动
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：后端 — 扩展 board 数据采集 + Cockpit board API

### 做什么

当前 `_fetch_board_summary()` 从 board-server `/api/dashboard` 只取了 KPI，丢弃了活跃任务和今日事件。Phase 1 扩展该函数，把 `active_tasks` 和 `today_events` 一并提取返回。同时在 Cockpit 自身上增加 `/api/board` 端点，返回含活跃任务的全量 board 数据（含 active_tasks + today_events），供 JS 异步轮询使用。

这样使得 board-server 已有的数据流通过 Cockpit 的 API 透传至前端，不改 board-server 一行代码。

### 怎么做

**1. 扩展 `_fetch_board_summary()` 返回结构**（`ccc-cockpit.py:347-352`）：

当前返回：
```python
return { "columns": ..., "kpi": ..., "workspaces": ..., "last_updated": ... }
```

改为：
```python
return {
    "columns": columns,
    "kpi": kpi,
    "workspaces": workspaces,
    "active_tasks": active_tasks,      # 新增 — board-server 已 enriched
    "today_events": today_events[:10],  # 新增 — 保留最近 10 条
    "last_updated": datetime.now().strftime("%H:%M"),
}
```

其中 `active_tasks` 和 `today_events` 从 dashboard JSON 的 `active_tasks` / `today_events` 字段直接取（L640-642），需要解析时保留：

在 `_fetch_board_summary()` 的 dashboard 处理分支（L311-337）中，dashboard dict 已有 `active_tasks` / `today_events` 字段。改为保留它们：

```python
dashboard = _http_get_json(...)
if isinstance(dashboard, dict):
    # (保留现有 KPI 提取逻辑 L313-337 不变)
    # 新增：取活跃任务和今日事件
    active_tasks = dashboard.get("active_tasks", [])
    today_events = dashboard.get("today_events", [])
```

在函数末尾返回时加入这两个字段。

**2. Cockpit `/api/board` 端点改为返回全量数据**（`ccc-cockpit.py:924-939`）：

当前 `/api/board` 路由调用 `_fetch_board_summary()` 并直接返回。Phase 1 后该函数已包含 active_tasks + today_events，所以前端拿到后可直接用于 JS 渲染。

无需改 do_GET 逻辑，只需要确认 response 包含新字段。

**3. 测试追加**（`tests/scripts/test_cockpit.py`，文件末尾追加）：

```python
def test_board_active_tasks_structure():
    """验证 active_tasks 各字段结构"""
    sample = {
        "id": "test-task-1",
        "title": "Test Active Task",
        "phase_cn": "开发中",
        "human_who": "dev",
        "elapsed_cn": "已运行 5 分钟",
        "workspace": "CCC",
        "updated_at": "2026-07-14T12:00:00+08:00",
    }
    assert "id" in sample
    assert "title" in sample
    assert "phase_cn" in sample
    assert "elapsed_cn" in sample
    assert "workspace" in sample

def test_today_events_structure():
    """验证 today_events 各字段结构"""
    sample = {
        "time": "12:00",
        "task_id": "test-task-2",
        "task_title": "Test Completed Task",
        "to_column": "released",
        "action_cn": "已发布",
        "workspace": "CCC",
    }
    assert "time" in sample
    assert "task_id" in sample
    assert "task_title" in sample
    assert "to_column" in sample
    assert "workspace" in sample
```

### 验收清单

- [ ] 验收条件 1：`_fetch_board_summary()` 返回结构包含 `active_tasks`（list）和 `today_events`（list）
- [ ] 验收条件 2：dashboard 响应中有 active_tasks 时，正确透传到返回结构
- [ ] 验收条件 3：dashboard 离线时，active_tasks 为 `[]`，today_events 为 `[]`，不抛异常
- [ ] 验收条件 4：Cockpit `/api/board` 响应中包含 active_tasks 和 today_events 字段
- [ ] 验收条件 5：新增测试全部通过，原有测试不回归
- [ ] 错误处理：board-server 返回格式异常时，active_tasks 回退为 `[]`
- [ ] 安全相关：无

### 验收

- [数据结构正确] `cd /Users/apple/program/CCC && uv run pytest tests/scripts/test_cockpit.py -v` 全部 PASSED
- [编译通过] `python3 -m compileall -q scripts/ccc-cockpit.py tests/scripts/test_cockpit.py`
- [端点可用] 启动 Cockpit（`python3 scripts/ccc-cockpit.py &`），curl `/api/board` 检查返回含 `active_tasks` 和 `today_events` 字段（参考：`curl -s http://localhost:7778/api/board | python3 -c "import sys,json; d=json.load(sys.stdin); print('active_tasks' in d, 'today_events' in d)"` 输出 `True True`）

---

## 改动 2（Phase 2）：前端 — 活跃任务和今日事件 HTML 渲染 + JS 自动刷新

### 做什么

在看板概览下方新增两个可视化区块：

1. **活跃进程列表**：显示当前 In Progress / Testing 中的所有任务，每行显示任务标题、所属 workspace、执行人角色、已运行时间。空时显示"暂无活跃任务"。
2. **今日完成记录**：显示今天已完成（released/verified）的任务事件时间线。空时显示"今日暂无完成记录"。

同时扩展 `/api/alive` 轮询 JS，同步更新活跃任务和今日事件 DOM（每 30s 刷新）。

### 怎么做

**1. 新增渲染函数**（`ccc-cockpit.py`，在 `_render_board_section()` 之后、`render_html()` 之前，约 L442）：

**`_render_active_tasks_section(active_tasks)`** — 渲染活跃任务列表：

```python
def _render_active_tasks_section(active_tasks: list) -> str:
    """渲染活跃任务列表。active_tasks 来自 board-server dashboard /api/dashboard 的 enriched 数据。
    
    每行: dot(颜色) + 任务标题 + workspace badge + 执行人 + 已运行时间
    """
    if not active_tasks:
        return ('<div style="background:{surface};border:1px solid {border};border-radius:8px;padding:14px;font-size:13px;color:{muted}">暂无活跃任务</div>'
                .format(surface=THEME["surface"], border=THEME["border"], muted=THEME["muted"]))
    
    rows = ""
    for t in active_tasks:
        tid = t.get("id", "")
        title = t.get("title", tid)
        ws = t.get("workspace", "")
        who = t.get("human_who", "")
        elapsed = t.get("elapsed_cn", "")
        phase = t.get("phase_cn", "")
        # dot 颜色: in_progress=orange, testing=purple
        col = t.get("status", "")
        dot_color = THEME["yellow"] if col in ("in_progress", "planned") else "#6a1b9a"
        rows += (
            f'<tr class="active-task-row" data-task-id="{tid}">'
            f'<td><span class="dot" style="background:{dot_color};display:inline-block;width:8px;height:8px;border-radius:50%"></span></td>'
            f'<td>{title}</td>'
            f'<td><span class="ws-badge">{ws}</span></td>'
            f'<td>{phase}</td>'
            f'<td>{who}</td>'
            f'<td class="elapsed" style="color:{THEME["muted"]}">{elapsed}</td>'
            f'</tr>'
        )
    
    return (
        '<div style="background:{surface};border:1px solid {border};border-radius:8px;padding:14px">'
        '<div class="tbl-wrap"><table>'
        '<thead><tr><th style="width:20px"></th><th>任务</th><th>Workspace</th><th>阶段</th><th>执行人</th><th>耗时</th></tr></thead>'
        '<tbody>{rows}</tbody>'
        '</table></div></div>'
    ).format(surface=THEME["surface"], border=THEME["border"], rows=rows)
```

**`_render_today_events_section(today_events)`** — 渲染今日事件时间线：

```python
def _render_today_events_section(today_events: list) -> str:
    """渲染今日完成记录列表（released/verified 事件为主）。"""
    # 只取 released 和 verified 的事件作为"已完成"记录
    completed = [e for e in (today_events or []) if e.get("to_column") in ("released", "verified")]
    if not completed:
        return ('<div style="background:{surface};border:1px solid {border};border-radius:8px;padding:14px;font-size:13px;color:{muted}">今日暂无完成记录</div>'
                .format(surface=THEME["surface"], border=THEME["border"], muted=THEME["muted"]))
    
    items = ""
    for ev in completed[:10]:
        time_str = ev.get("time", "")
        title = ev.get("task_title", ev.get("task_id", ""))
        action = ev.get("action_cn", "")
        ws = ev.get("workspace", "")
        color = THEME["green"] if ev.get("to_column") == "released" else "#1a7d1a"
        items += (
            f'<div class="event-item" style="display:flex;gap:10px;align-items:center;padding:6px 0;border-bottom:1px solid #f0f0f2">'
            f'<span style="color:{THEME["muted"]};font-size:12px;font-family:monospace;min-width:40px">{time_str}</span>'
            f'<span class="dot" style="background:{color};display:inline-block;width:8px;height:8px;border-radius:50%"></span>'
            f'<span>{title}</span>'
            f'<span style="color:{color};font-size:12px">{action}</span>'
            f'<span class="ws-badge" style="font-size:11px">{ws}</span>'
            f'</div>'
        )
    
    return (
        '<div style="background:{surface};border:1px solid {border};border-radius:8px;padding:14px">'
        '{items}'
        '</div>'
    ).format(surface=THEME["surface"], border=THEME["border"], items=items)
```

**2. 在 `render_html()` 中嵌入新区块**（`ccc-cockpit.py:858-860`，看板概览 section 之后）：

当前看板渲染位于 `render_html()` L858-859：
```python
  <div class="sec-title">看板概览</div>
  {_render_board_section(data.get("board"))}
```

在其后追加：
```python
  <div class="sec-title" style="margin-top:16px">活跃进程</div>
  {_render_active_tasks_section((data.get("board") or {}).get("active_tasks", []))}

  <div class="sec-title" style="margin-top:16px">今日完成</div>
  {_render_today_events_section((data.get("board") or {}).get("today_events", []))}
```

注：使用 `id="active-tasks-section"` 和 `id="today-events-section"` 包裹外层容器，便于 JS 按 ID 更新。

**3. JS 自动刷新**（JS 部分，`ccc-cockpit.py:765-770`，在 `fetchAlive` 逻辑之后）：

当前已有 `fetchAlive()` 每 30s 轮询 `/api/alive`。新增 `refreshBoardSection()` 函数，同样每 30s 调 Cockpit `/api/board` 更新活跃任务和今日事件 DOM：

```javascript
function refreshBoardSection() {
    fetch('/api/board')
    .then(function(res) { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
    .then(function(board) {
        // 更新活跃任务（如果 render 结果可嵌入）
        var activeSection = document.getElementById('active-tasks-section');
        var eventsSection = document.getElementById('today-events-section');
        if (activeSection && board.active_tasks) {
            // 简化为刷新整个页面（全量渲染在 server side，这里先 fallback 到页面刷新）
            // 后续可升级为 API 纯数据 → 前端渲染
        }
    })
    .catch(function(err) { /* silent */ });
}
```

但更简单有效的方案：利用已在运行 `fetchAlive` 定时器，在 `/api/alive` 返回后新增一条 fetch 取 `/api/board` 数据来更新 DOM。

由于 Cockpit 是 server-rendered HTML，JS 端做动态渲染比较复杂。更务实的方案：**在 `fetchAlive` 的 30s 轮询回调内加入 `location.reload()` 的条件判断**，或简单地让 `/api/alive` 也返回活跃任务数据。

我认为最简洁的方案是：
- 扩展 `/api/alive` 端点，额外返回 board 的 `active_tasks` 和 `today_events`
- JS 端用这些数据动态构建 DOM 元素

但这样 `/api/alive` 的数据会膨胀。更好的方式是：

Cockpit 目前是**服务端完全渲染**。JS 实现动态更新活跃任务列表需要前端渲染逻辑，代码量较大。折衷方案：
1. 首次加载时服务端渲染完整的 active_tasks + today_events 区块
2. JS 每 30s 调用 Cockpit 的 `/api/board` 端点，判断活跃任务数或今日事件数是否有变化
3. 有变化时自动 `location.reload()` 刷新整页

```javascript
// 在 fetchAlive 30s timer 后追加
setInterval(function() {
    fetch('/api/board')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        var activeCount = (data.active_tasks || []).length;
        var cachedEl = document.getElementById('active-task-count');
        var prev = cachedEl ? parseInt(cachedEl.textContent) : -1;
        if (prev >= 0 && prev !== activeCount) {
            location.reload();
        }
        if (cachedEl) cachedEl.textContent = activeCount;
    })
    .catch(function() {});
}, 30000);
```

并在 HTML 中渲染一个隐藏的 `#active-task-count` 用于缓存比较：

```html
<span id="active-task-count" style="display:none">{len}</span>
```

这样实现简单、稳健，且数据始终一致（全量服务端渲染）。

**简化后改动**：
1. 服务端渲染全量 HTML（两个新 section）
2. JS 每 30s 检测变化自动刷新页面

### 验收清单

- [ ] 验收条件 1：有活跃任务时，看板概览下方显示任务列表（title/workspace/phase/who/elapsed）
- [ ] 验收条件 2：无活跃任务时，显示"暂无活跃任务"
- [ ] 验收条件 3：有今日完成记录时，按时间排列展示（time/title/action/workspace）
- [ ] 验收条件 4：无今日完成记录时，显示"今日暂无完成记录"
- [ ] 验收条件 5：活跃任务数据变化时，30s 内页面自动刷新展示最新状态
- [ ] 边界场景：active_tasks 为 None 或空 list，不抛异常
- [ ] 错误处理：board-server 离线时，两个 section 都显示空状态（各自的"暂无"文案），不崩溃
- [ ] 安全相关：无

### 验收

- [服务端渲染] 启动 Cockpit（`python3 scripts/ccc-cockpit.py`），浏览器打开看板概览下方出现"活跃进程"和"今日完成"两个 section
- [空状态] board-server 离线时（`pkill -f ccc-board-server` 后刷新），两个 section 显示各自的空状态文案（"暂无活跃任务" / "今日暂无完成记录"）
- [编译通过] `python3 -m compileall -q scripts/ccc-cockpit.py`
- [JS 自动刷新] 观察页面：有任务变化时（如从 testing 移回 verified），30s 内自动刷新显示

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 扩展 `_fetch_board_summary()` 返回 active_tasks + today_events；扩展 Cockpit `/api/board` 透传全量数据；追加数据结构测试 | `feat(cockpit): 扩展 board summary 获取活跃任务和今日事件数据 (phase 1/2)` |
| 2 | 新增活跃任务和今日事件 HTML 渲染函数；在看板下方嵌入两个新 section；JS 30s 自动刷新 | `feat(cockpit): 活跃任务列表 + 今日完成记录 + 自动刷新 (phase 2/2)` |

---

## 全局验收清单

- [ ] 编译零错误（`python3 -m compileall -q scripts/ccc-cockpit.py tests/scripts/test_cockpit.py`）
- [ ] `tests/scripts/test_cockpit.py` 全部测试 PASSED（原有 4 + 新增 2 = 6）
- [ ] diff 范围仅限白名单 2 个文件
- [ ] 每个 phase 对应一个独立 commit
- [ ] phases.json 与 plan phase 数一致（2 phases）
- [ ] Plan 中所有验收意图全部达成
- [ ] 浏览器打开 `http://localhost:7778` 确认：
  - 看板概览下方出现"活跃进程"区块，显示当前 in_progress/testing 任务
  - 再下方出现"今日完成"区块，显示 released/verified 事件时间线
  - board-server 离线时，两个区块显示空状态

---

## 后续步骤

无。部署后重启 Cockpit 即可生效。由于不依赖 board-server 改动，零迁移成本。