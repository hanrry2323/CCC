# CCC 线路图重构代码库审查与设计报告

> 日期：2026-08-12 · 调研员：OpenCode · 核心标准依据：`docs/CCC-PRIME-DIRECTIVE.md` (最高准则 v1.0)

根据 CCC 最高准则，未来的系统需要达成「**线路图管未来，计划管当前，看板管正在进行时**」的三层级联金字塔。当前基于 `type == 'epic'` 临时任务卡的动态推导机制属于重构前的临时过渡，不符合里程碑作为“一等公民”且具备 Project + Milestone + Step 独立持久化的长远目标。

以下是针对该目标重构代码库的详细审查与方案清单：

---

## 一、 现有代码完整模块清单 (核心函数与类)

### 1. 方案池逻辑层 (`server/board/plans.py`)
*   `list_plans(repo_root, project, status, q)`：列出全部方案，目前根据卡头 `状态：` 字段返回五态中的一种。
*   `get_plan(repo_root, rel_path)`：读取单篇方案详情，并动态提取其 `## 验收标准` checkbox 达成度。
*   `create_plan(...)`：创建新方案并自动自增编号落盘。**（重构切入点：默认状态不可再为“草案”，应跟随“已确认”作为起点）**。
*   `update_plan(...)`：依据 `_TRANSITIONS` 状态流转白名单，更新状态或内容。**（重构切入点：流转需要将“草案”剔除）**。
*   `convert_plan(...)`：利用 `fcntl` 进程锁，解析 `## 转卡计划` 字段并调用 `new-card.sh` 拆卡。

### 2. 看板与史诗派生层 (`server/board/loader.py`)
*   `load_dispatch_cards_incremental(...)`：看板卡片的增量加载核心。
*   `derive_epic_states_and_progress(items)`：**（重构最大切入点）**。目前它是将 `type == 'epic'` 的 BoardItem 通过匹配其子卡 `parent` 进行进度 `closed/total` 动态派生。需要重构为真正读取独立持久化里程碑数据的模式。

### 3. API 控制层 (`server/web/server.py`)
*   `_handle_plans_list` 与 `_handle_plans_card_states`：提供方案池检索及卡片六列分布。
*   `path == "/board/roadmap"` 和 `/board/roadmap/<project>` 路由分发器：目前返回派生后的史诗数据。

### 4. 前端展现层 (`server/web/legacy-chat/js/pages/`)
*   `plansPage.js`：方案池视图。目前维护 `['草案', '已确认', '部分执行', '已完成', '作废']` 五态列。**（重构切入点：移除“草案”列）**。
*   `roadmapPage.js`：线路图页面。目前渲染左侧时间线与右侧史诗面板。**（重构切入点：需要重构出独立的 Milestone/Project 和一个在页面底侧或左侧常驻的“草案池”区域）**。

---

## 二、 系统架构重构设计 (API 到前端数据流图)

```text
 ┌────────────────────────────────────────────────────────┐
 │            1. 线路图层 (未来意图 & 里程碑)              │
 │  数据：data/roadmap/roadmap.json (独立 Project 模型)     │
 │  接口：GET /roadmap/projects ──▶ roadmapPage.js         │
 │  [草案池常驻于此，老板确认后转入计划。里程碑状态全自动回写]│
 └──────────────────────────┬─────────────────────────────┘
                            │
                  ① 老板确认 Milestone (转为 Plan)
                            │
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │                2. 计划池层 (当前执行)                   │
 │  数据：docs/projects/<prefix>/plans/*.md (Plan 文件)   │
 │  接口：GET /plans/list (仅 已确认/部分执行/已完成 三态)   │
 │  流转：plansPage.js ────▶ 状态由子卡关闭率自动回写       │
 └──────────────────────────┬─────────────────────────────┘
                            │
                  ② 老板确认转卡 (convert)
                            │
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │               3. 看板层 (正在进行时)                     │
 │  数据：docs/dispatch/ (Card 任务卡 Markdown)            │
 │  接口：GET /board/snapshot ──▶ boardPage.js            │
 │  [Engine 闭环自动流转 5 列 ──▶ ③ 合入批准 ──▶ 部署]     │
 └────────────────────────────────────────────────────────┘
```

---

## 三、 需要修改的文件清单 (按改动范围降序)

### 1. `server/web/legacy-chat/js/pages/plansPage.js` (改动范围：大)
*   **改动**：状态定义 `STATUSES` 缩窄为 `['已确认', '部分执行', '已完成', '作废']`（移去 `草案`）。合并前端 UI 列数，重排宽度占比。

### 2. `server/web/legacy-chat/js/pages/roadmapPage.js` (改动范围：大)
*   **改动**：从 `/roadmap/projects` 读取全新 Project + Milestone 数据。在页面显式增加 **「草案池 / 远期讨论意图」** 侧边卡片箱或新区域，支持将草案在此列出并提供「一键升级为里程碑」的人工动作。

### 3. `server/board/plans.py` (改动范围：中)
*   **改动**：
    1.  `create_plan` 移除 `状态：草案` 默认设定，改为支持直接根据关联里程碑状态初始化为 `已确认`。
    2.  `_TRANSITIONS` 去除包含 `草案` 的流转控制链。

### 4. `server/board/loader.py` (改动范围：中)
*   **改动**：修改 `derive_epic_states_and_progress` 逻辑，将计算闭合率后回写的终点从“仅修改 BoardItem 标题字符串”升级为：**实时读取并解析、改写物理 Project 配置文件及对应的里程碑进度**，真正达成数据级级联。

### 5. `server/web/server.py` (改动范围：小)
*   **改动**：
    1.  移除 `/board/roadmap` 对旧 Epic 派生的强耦合逻辑。
    2.  新增 `/roadmap/projects` (获取独立里程碑)、`/roadmap/update` (改写 Project 元数据) 端点。

### 6. `docs/DOC-PROTOCOL.md` (改动范围：小)
*   **改动**：修改第 2.8 节方案状态机文字定义（五态降为三执行态），将草案管理归属于线路图章节说明。

---

## 四、 需要新增的文件清单

1.  **`server/board/roadmap_store.py` (数据持久化模型)**：
    *   独立 Project/Milestone/Step 数据模型类，并提供 `load_roadmap()`、`save_roadmap()`、以及级联回写 `update_milestone_progress(plan_id)` 核心方法。
    *   默认持久化落点：`data/roadmap/roadmap.json`。
2.  **`server/tests/test_roadmap_rebuild.py` (单元测试防退化)**：
    *   对 Milestone 级联进度计算、草案移动、以及三执行态转换边界进行测试覆盖。

---

## 五、 需要删除的代码清单

1.  `server/board/loader.py` 中过时的基于 `item.type == 'epic'` 临时强猜的子卡和进度匹配拼接硬编码：
    ```python
    # 彻底删除以下旧格式化拼接：
    title=f"{item.title} ({progress_str})"
    ```
2.  `plansPage.js` 中渲染 `草案 / 待讨论` 物理列所声明的 DOM 节点以及草案直接移动的 `STATE_FLOW['草案']` 逻辑。
