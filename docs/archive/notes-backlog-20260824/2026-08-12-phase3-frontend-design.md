# Phase 3 前端改造具体方案

> 日期：2026-08-12 · 只读分析，不改代码

---

## 文件清单

| 文件 | 作用 | 改动范围 |
|------|------|---------|
| `server/web/legacy-chat/js/pages/plansPage.js` | 计划页面 | 草案列标记、列宽、数据源 |
| `server/web/legacy-chat/js/pages/roadmapPage.js` | 线路图页面 | 全面重构：读 roadmap.md 数据 |
| `server/web/legacy-chat/js/roadmapTimeline.js` | SVN/里程碑渲染器 | 新增草案池渲染、进度条 |
| `server/web/legacy-chat/index.html` | HTML 模板 | 无结构改动（route 已存在） |
| `server/web/legacy-chat/js/app.js` | 路由 | 无改动（route 已存在） |

---

## 一、plansPage.js — 草案列改造

### 1.1 草案列标记（第 18 行）

```js
// 当前（第 18 行）
const STATUSES = ['草案', '已确认', '部分执行', '已完成', '作废'];
```

**改动**：在草案列标题加一个标签，说明草案来自 roadmap.md 草案池。

```js
// 改后
const STATUSES = ['草案', '已确认', '部分执行', '已完成', '作废'];
const STATUS_HINTS = {
  '草案': '来自线路图草案池',
  '已确认': '待排期',
  '部分执行': '已转卡',
  '已完成': '卡全关',
  '作废': '不执行',
};
```

### 1.2 renderColumn 函数（第 218-234 行）

**改动**：草案列使用 `STATUS_HINTS` 而非硬编码 `hints` 对象。

```js
// 当前（第 222 行）
const hints = { '草案': '待讨论', ... };

// 改后
const hint = STATUS_HINTS[status] || '';
```

### 1.3 列宽 CSS（第 279-284 行 `applyFlowColumns`）

**改动**：草案列宽调大（草案是流程起点，需要更多空间显示方案标题）。

```js
// 当前（第 283 行）
flow.style.gridTemplateColumns = `repeat(${Math.max(1, visible)}, minmax(0, 1fr))`;

// 改后：草案列占 1.5 倍宽度
if (!_hideClosed) {
  flow.style.gridTemplateColumns = `1.5fr repeat(${STATUSES.length - 2}, 1fr)`;
} else {
  flow.style.gridTemplateColumns = `1.5fr repeat(${Math.max(1, STATUSES.length - 3)}, 1fr)`;
}
```

### 1.4 数据源（第 124-144 行 `loadPlans`）

**无改动**：方案列表数据源不变（`GET /plans/list`）。草案状态来自方案文件的 `状态：草案`，不是从 roadmap.md 直接读取——两者应保持一致（roadmap.md 草案池中的条目应已转方案）。

---

## 二、roadmapPage.js — 全面重构

### 2.1 当前问题

当前 `roadmapPage.js` 完全依赖 `GET /board/roadmap` API 返回的 `business_lines` 数据（旧 epic 卡模型），但 ccc02 已改为 `roadmap.py` 数据模型。API 返回格式已变（`roadmaps` 数组而非 `business_lines`）。

### 2.2 重构方案

#### 2.2.1 一级页：项目卡片（第 47-127 行）

**当前**：`renderOverview(data)` 取 `data.business_lines`。

**改后**：取 `data.roadmaps`，每个项目显示草案池条目数 + 里程碑数 + 进度。

```js
// 改后的 renderOverview（伪代码）
function renderOverview(data) {
  const roadmaps = data.roadmaps || [];
  // 每个 roadmap 渲染为项目卡片：
  //   - 项目名 + 草案数 + 里程碑数
  //   - 总进度条（所有里程碑的关联方案完成率）
  //   - 点击进入二级页
}
```

**具体改动位置**：

| 行号 | 函数 | 当前行为 | 改后行为 |
|------|------|---------|---------|
| 47-95 | `projectCard()` | 取 `section.milestones` 和 `m.cards`（旧 epic 卡字段） | 取 `roadmap.drafts` 和 `roadmap.milestones`；进度 = 关联方案完成率 |
| 97-127 | `renderOverview()` | 取 `data.business_lines` | 取 `data.roadmaps`；筛选器按里程碑状态过滤 |

#### 2.2.2 二级页：单项目线路图（第 129-170 行）

**当前**：`openProject(project)` → `GET /board/roadmap/<project>` → 渲染 SVG 时间线 + 里程碑列表 + 卡分组。

**改后**：新增草案池区域 + 里程碑进度条。

```js
// 改后的 openProject 渲染结构
async function openProject(project) {
  const detail = await apiGet(`/board/roadmap/${encodeURIComponent(project)}`);
  body.innerHTML = `
    <div class="rm2">
      ${buildOverview(detail)}          // 顶部统计条（保持）
      ${buildDraftPool(detail.drafts)}  // 新增：草案池区域
      <div class="rm2-body">
        <div class="rm2-rail-wrap">
          <div class="rm2-rail-title">里程碑</div>
          ${buildMilestoneRail(detail)}  // 里程碑时间线（保持）
        </div>
        <div class="rm2-panel-wrap">...</div>
      </div>
      ${riskHTML(detail)}              // 风险提示（如果 API 提供）
    </div>`;
}
```

**新增 `buildDraftPool` 函数**（在 `roadmapTimeline.js` 中）：

```js
export function buildDraftPool(drafts) {
  if (!drafts || !drafts.length) return '';
  return `<div class="rm2-drafts">
    <strong>草案池（${drafts.length}）</strong>
    <div class="rm2-draft-list">
      ${drafts.map(d => `<div class="rm2-draft-item">
        <span class="rm2-draft-title">${esc(d.title || d)}</span>
        <span class="rm2-draft-tag">草案</span>
      </div>`).join('')}
    </div>
  </div>`;
}
```

**新增里程碑进度条**（在 `milestonePanelHTML` 中）：

每个里程碑面板显示关联方案完成率进度条。

```js
// 在 milestonePanelHTML 中新增（第 204-217 行之间）
function buildProgressBar(completed, total) {
  if (!total) return '';
  const pct = Math.round((completed / total) * 100);
  return `<div class="rm2-mile-progress">
    <div class="rm2-progress-track"><div class="rm2-progress-fill" style="width:${pct}%"></div></div>
    <span class="rm2-progress-label">${completed}/${total} 方案已完成</span>
  </div>`;
}
```

### 2.3 具体改动位置汇总

| 文件 | 行号 | 改动 |
|------|------|------|
| `roadmapPage.js:49-95` | `projectCard()` | 字段映射：`m.cards` → `roadmap.milestones`；新增草案计数 |
| `roadmapPage.js:97-127` | `renderOverview()` | `data.business_lines` → `data.roadmaps` |
| `roadmapPage.js:131-155` | `openProject()` | 新增 `buildDraftPool()` 调用 |
| `roadmapTimeline.js:最后` | 新增 | `buildDraftPool()` 函数 |
| `roadmapTimeline.js:183-217` | `milestonePanelHTML()` | 新增进度条 `buildProgressBar()` |
| `plansPage.js:18` | `STATUSES` | 新增 `STATUS_HINTS` |
| `plansPage.js:222` | `renderColumn()` | `hints` → `STATUS_HINTS[status]` |
| `plansPage.js:283` | `applyFlowColumns()` | 草案列 1.5x 宽度 |

---

## 三、API 数据格式对齐

### 3.1 当前 API 返回格式

`GET /board/roadmap` 返回：
```json
{
  "roadmaps": [
    {
      "project": "ccc",
      "drafts": ["草案标题1", "草案标题2"],
      "milestones": [
        {"title": "M1", "status": "进行中", "linked_plans": ["ccc-plan-001"], "description": "..."}
      ],
      "updated": "2026-08-12"
    }
  ],
  "total": 1
}
```

### 3.2 需要补充的 API 字段

二级页 `GET /board/roadmap/<project>` 需要返回：
- `drafts` 数组（每个草案的标题）
- `milestones` 数组（每个里程碑的 `title`/`status`/`linked_plans`/`description` + 计算字段 `progress_pct`/`completed`/`total`）
- `updated` 日期

**当前 API 实现**（第 2943-2948 行 `server.py`）已有 `roadmap_parser` 回退——但格式可能与前端期望不匹配。Phase 4 需统一 API 数据格式。

---

## 四、CSS 改动（不在 JS 文件中，但需新增）

`server/web/legacy-chat/css/` 中需新增：
- `.rm2-drafts` — 草案池容器
- `.rm2-draft-item` — 草案条目
- `.rm2-mile-progress` — 里程碑进度条
- `.pcol:first-child` — 草案列宽 1.5x

---

## 五、不改动的文件

- `index.html`：route 结构已存在（`#/plans`、`#/roadmap`）
- `app.js`：路由逻辑已存在（`mountPlans`/`mountRoadmap`）
- `server.py`：API 端点已存在（`/board/roadmap`、`/plans/*`）
- `roadmap.py`：数据模型已就绪（Phase 1 完成）