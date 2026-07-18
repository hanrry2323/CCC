# Plan: cockpit-queue-display — Cockpit 显示排队队列深度

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-cockpit.py`（~1000 行）
- **当前结构要点**：
  1. `_fetch_board_summary()`（L260-364）从 board-server（:7777）取看板数据，通过 `/api/board` 和 `/api/dashboard` 两个端点
  2. `/api/board` 返回 `{"columns": {backlog: [{id,title,ts,...}, ...], planned: [{...}], ...}, "counts": {...}}` — 每个列返回完整任务对象，但 Cockpit 当前只读 counts（L300：`columns[k] = int(cols[k])`），丢弃了实际任务数据
  3. `/api/dashboard` 返回 `today_events` 数组，每条含 `time`（HH:mm）、`task_id`、`to_column`（目标列）、`action_cn`、`workspace`。可以用来推算处理速率：统计 `to_column == "in_progress"` 的数量 / 今日已过小时数
  4. `_render_board_section()`（L387-453）渲染列卡片 + KPI pills，无队列详情区域
  5. Backlog 任务有 `ts` 字段（ISO 到达时间戳），Planned 任务有 `created_at` / `updated_at`（移到 planned 的时间以 `updated_at` 为准）
  6. `build_cockpit_data()`（L166）调用 `_fetch_board_summary()`，返回 `data["board"]` 给 render
  7. 页面自动刷新（`setInterval(fetchAlive, 30000)`）只刷新端口探测，不刷新看板数据
- **待改动点**：
  - `scripts/ccc-cockpit.py` 中 `_fetch_board_summary()`：提取 backlog/planned 任务列表 + 计算处理速率 + 为每个任务预估等待
  - `scripts/ccc-cockpit.py` 中 `_render_board_section()`：新增"队列详情"子区域，显示任务表

---

## 范围

- **目标**：在看板概览区下方增加 backlog/planned 队列详情，显示每个任务标题、到达时间、预估等待时长
- **只改文件**：`["scripts/ccc-cockpit.py"]`
- **不改文件**：`["scripts/ccc-board-server.py", "scripts/_board_store.py", "scripts/ccc-board.py", "scripts/ccc-engine.py"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：Cockpit 增加队列详情显示

### 做什么

在看板概览区域新增"队列详情" subsection，展示 backlog 和 planned 列中的任务级信息。用户进入 Cockpit 就能看到：

1. **排队列表**：backlog 和 planned 两个队列，每个任务显示序号、标题、已等待时长
2. **预计等待**：基于当前处理速率推算每个任务还要等多久
3. **无 API 时优雅降级**：board-server 离线时显示"看板服务离线"，不报错

**核心设计**：不新增 API 端点 — `/api/board` 已返回完整任务数据，`/api/dashboard` 已返回今日事件。Cockpit 侧提取并增强展示即可。计算逻辑全在 `ccc-cockpit.py` 内，对 board-server 零侵入。

### 怎么做

#### 1a. `ccc-cockpit.py` — `_fetch_board_summary()` 中新增 queue_detail 提取

当前位置：L295-305（`board = _http_get_json(...)` 之后）。在现有的列计数提取（L299-304）之后，插入 backup/planned 任务提取逻辑：

从 `cols` 的 `"backlog"` 和 `"planned"` 数组中提取每个任务的 `id`、`title`、`ts`（backlog）或 `updated_at`（planned）。对提取的任务按时间戳升序排列。

**注意**：backlog 任务的 `ts` 字段名可能是 `"ts"`（从任务 JSONL 模板来），也可能有 `"created_at"`。优先读 `ts`，回退到 `created_at`。planned 任务的到达时间用 `updated_at`（因为从 backlog 移到 planned 时更新了这个字段）。时间戳字符串统一截取前 19 字符（`YYYY-MM-DDTHH:MM:SS`），忽略时区后缀用于显示。

#### 1b. `ccc-cockpit.py` — 处理速率推算

在 Dashboard 数据获取（L310-353）之后，从 `today_events` 中统计 `to_column == "in_progress"` 的事件数量作为今日处理量。

计算逻辑：
- `completed_today = len([ev for ev in today_events if ev.get("to_column") == "in_progress"])`
- 如果今日有事件数据：`hours_today = max(当前时 + 当前分/60 - 最早事件时, 1)`，`rate_per_task_min = hours_today * 60 / max(completed_today, 1)`
- 如果今日无事件数据：使用默认值 30 min/task
- rate 上限 120 min/task（防止全空转假场景下无限推估）

#### 1c. `ccc-cockpit.py` — 队列详情计算

对 backlog 和 planned 的每个任务计算预估等待时长：

- **backlog 第 N 个任务**：预估等待 ≈ `(N + len(planned)) * rate_per_task_min`
- **planned 第 N 个任务**：预估等待 ≈ `(N+1) * rate_per_task_min`（planned 队首就是下一个要执行的）

预估等待展示为人类可读格式：
- `< 30min` → "约 N 分钟"
- `30-120min` → "约 N 小时 N 分"
- `> 120min` → "> 2 小时"

#### 1d. `ccc-cockpit.py` — `_render_board_section()` 中新增队列详情 HTML

在原有的 board cards + KPI pills 区域之后（L452），新增一个"队列详情"子区域。

布局：
1. 一个 `<div>` 区域，标题 "队列详情"
2. 两个子表（backlog / planned），各含表头：
   - `#`（序号）
   - `任务`（标题，截断到 40 字符 + `...`）
   - `等待`（任务已在队列中的时长，从到达时间到现在的差值，格式同预估等待）
   - `预估`（预估剩余等待时长）
3. backlogs 子表使用灰色（`#9aa0a6`）侧边色，planned 使用蓝色（`#1976d2`）
4. 如果队列为空，显示 "队列为空" 灰字提示
5. 当 `board is None`（board-server 离线）时，整个看板概览区域包括队列详情不渲染

**CSS 注意事项**：当前 `render_html()` 里 CSS inline 写死的。新增的队列详情样式直接 inline 或复用现有 CSS 变量。不增加外部 CSS 文件。

### 验收清单

- [ ] backlog/planned 任务列表正确从 `/api/board` 响应中提取
- [ ] 时间戳正确解析并显示为"已等待 XXX"格式
- [ ] 预估等待基于今日处理速率推算，默认值回退 30min/task
- [ ] 处理速率上限 120min/task
- [ ] board-server 离线时优雅降级（不崩溃，显示"看板服务离线"）
- [ ] 队列为空时显示"队列为空"提示
- [ ] 标题过长时截断到 40 字符
- [ ] `python3 -m compileall -q scripts/ccc-cockpit.py` 零错误
- [ ] 页面在浏览器正常渲染（`http://localhost:7778`）

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-cockpit.py` → 0 errors
- [启动检查] `timeout 5 python3 scripts/ccc-cockpit.py` → 启动正常，无 Exception
- [board-server 在线时] 页面看板概览区下方出现"队列详情"section，显示 backlog(5)+planned(2) 的任务列表，含等待时间和预估等待
- [board-server 离线时] board-section 显示"看板服务离线"，不抛 Exception
- [空队列时] 当 backlog+planned 均为空，"队列为空"提示可见
- [时间显示] 每个任务显示"已等待 30 分钟"或"已等待 1 小时 20 分"格式
- [预估合理] 预估等待个数与队列深度一致，不会出现 0 分钟（新任务的预估= (0+len(planned))*rate）
- [样式] backlog 列灰色侧边，planned 列蓝色侧边

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | Cockpit 新增队列详情显示：_fetch_board_summary 提取 backlog/planned 任务详情 + 处理速率推算 + _render_board_section 增加队列表 | `feat(cockpit): 看板首页增加队列详情（任务列表+等待时间+预估算） (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/ccc-cockpit.py`）
- [ ] 页面在浏览器正常渲染（`http://localhost:7778`）
- [ ] diff 范围仅限 `scripts/ccc-cockpit.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
- [ ] board-server 离线不崩溃（try-except 保护 API 调用链）

---

## 后续步骤

后续可考虑：
- Cockpit 页面自动刷新看板数据（当前只 30s 刷端口探测，看板数据只在首次加载时 fetch）。可加一个 60s 的 `setInterval` 刷 `#board-section`
- 估算模型可加入更多历史数据（最近 7 天平均处理量）替代仅今日统计
- 队列名称可改用中文（backlog → 待办池，planned → 待执行）