# CCC 看板线路图代码级分析

> 日期：2026-08-12 · 来源：`server/board/plans.py` + `server/web/server.py` + `DOC-PROTOCOL.md` + 前端 SPA + `validate-plans.sh` 源码走读
> 交叉验证对象：`docs/notes/2026-08-12-board-roadmap-analysis.md`（OpenCode/qx2 分析）

---

## 一、完整 API 端点清单

### 1.1 方案相关（/plans/*）

| 端点 | 方法 | 参数 | 返回值 | 鉴权 |
|------|------|------|--------|------|
| `/plans/list` | GET | `?project=<prefix>&status=<五态>&q=<关键词>` | `{plans: [{id, project, num, slug, title, status, author, tool, created, updated, cards, path, acceptance}], total}` | 需要 |
| `/plans/card-states` | GET | 无 | `{states: {plan_path: {total, cols: {待分派:n, 执行中:n, 机审:n, 已回写:n, 打回:n, 已关闭:n}}}}` | 需要 |
| `/plans/detail` | GET | `?path=<相对路径>` | `{id, project, num, slug, title, status, author, tool, created, updated, cards, related, path, content, acceptance}` | 需要 |
| `/plans/create` | POST | `{project, title, content, author, tool}` | `{ok, path, id}` 或 `{error}` | 需要 |
| `/plans/update` | POST | `{path, status?, content?, cards?}` | `{ok}` 或 `{error}` | 需要 |
| `/plans/convert` | POST | `{path}` | `{ok, cards: [id]}` 或 `{error, cards?, partial?}` | 需要 |

**头部文档缺失**：`server.py` 头部注释（第 19-27 行）列出了 `/plans/list`、`/plans/detail`、`/plans/create`、`/plans/update`、`/plans/convert`，但**遗漏了 `/plans/card-states`**（第 1995-2005 行实际存在）。

### 1.2 线路图相关（/board/roadmap*）

| 端点 | 方法 | 参数 | 返回值 | 鉴权 |
|------|------|------|--------|------|
| `/board/roadmap` | GET | 无 | `{overview: [{bucket, count}], by_project: [{project, count, buckets}], business_lines: [{project, milestones}]}` | 需要 |
| `/board/roadmap/<project>` | GET | 路径参数 | `{project, milestones, groups: {done, doing, planned}, counts, risks}` | 需要 |

### 1.3 看板相关（/board/*）

| 端点 | 方法 | 参数 | 返回值 |
|------|------|------|--------|
| `/board/realtime` | GET | 无 | `{列名: [{卡}]}` |
| `/board/recent` | GET | 无 | `[{卡}]` 7天回写窗口 |
| `/board/by_project` | GET | 无 | `[{project, count, states}]` |
| `/board/states` | GET | 无 | `{五态计数, columns, note}` |
| `/board/ready_for_merge` | GET | 无 | `{cards, count, threshold, backlog_alert}` |
| `/board/snapshot` | GET | `?workspace=` | `{columns, counts, workspace}` |
| `/board/summaries` | GET | `?workspaces=a,b` | `{summaries: {项目: snapshot}}` |
| `/board/arch` | GET | 无 | `{version, updated_at, gallery}` |

---

## 二、数据模型图

### 2.1 Plan 对象（内存 dict，非持久化模型）

```
Plan (dict)
├── id: str              # "{prefix}-plan-{num}"  例: ccc-plan-001
├── project: str         # 项目前缀 (2-4 小写字母)
├── num: str             # 三位序号 "001"
├── slug: str            # 标题转 slug
├── title: str           # 一级标题（去掉 "方案 · " 前缀）
├── status: str          # 五态之一
├── author: str          # 作者
├── tool: str            # 工具
├── created: str         # 创建日期 ISO
├── updated: str         # 更新日期 ISO
├── cards: str           # 关联卡列表，逗号分隔 "xy021, xy022"
├── related: str         # 关联方案 (仅 get_plan 返回)
├── path: str            # 相对路径 "docs/projects/ccc/plans/001-task.md"
├── content: str         # 完整 Markdown (仅 get_plan 返回)
├── acceptance: {total: int, done: int}  # 验收 checkbox 完成度
```

**物理存储**：`docs/projects/<prefix>/plans/<NNN>-<slug>.md`（纯 Markdown 文件，无数据库）

**文件头部格式**：
```markdown
# 方案 · <标题>

> 项目：ccc · 编号：ccc-plan-001 · 状态：草案 · 作者：张三 · 工具：Claude Code
> 创建：2026-08-12 · 更新：2026-08-12
> 关联卡：无
> 关联方案：无

## 目标
...
## 验收标准
- [ ] 项1
- [x] 项2
## 转卡计划
- 子任务1
- 子任务2
```

### 2.2 字段提取逻辑

| 字段 | 提取方式 | 文件位置 |
|------|---------|---------|
| title | `# 方案 · ...` 一级标题 | `_extract_title()` 搜前 5 行 |
| status/author/tool/cards | 头部 `> ` 行，用 `·` 分割，`键：值` 正则 | `_extract_header_fields()` 搜前 30 行 |
| acceptance | `## 验收标准` 节的 `- [x]` checkbox | `_extract_acceptance()` |
| 转卡计划 | `## 转卡计划` 到下一个 `## ` 之间 | `_convert_plan_locked()` |

### 2.3 方案与卡的关系

- **1:N**：一个方案可转出多张任务卡
- 关联方式：方案文件头部 `> 关联卡：ccc012, ccc013`
- 转卡时：`new-card.sh --project <prefix> --title "<方案标题> — <子任务标题>"`
- 编号独立：方案编号（`<prefix>-plan-<NNN>`）与卡编号（`<prefix><NNN>`）在不同的编号空间
- 保留表：`plan_reservations.py` 扫描方案文件的「关联卡」行，防止 `new-card.sh` 分配已被方案占用的卡编号

---

## 三、状态机完整转换图

### 3.1 DOC-PROTOCOL.md §2.8 声明的状态机

```
草案 → 已确认 → 部分执行 → 已完成
  ↓                           ↓
  └──────── 作废 ─────────────┘
```

文档描述为线性流程，但实际代码有差异。

### 3.2 plans.py 实际实现的状态机

```
                    ┌──────────────┐
                    │    草案      │
                    └──┬──────┬───┘
              已确认  │      │  作废
                    ┌─▼──────┐ │
                    │ 已确认  ├─┘
                    └──┬──────┘
              部分执行│      │  作废
                    ┌─▼──────┐ │
                    │部分执行 ├─┘
                    └──┬──────┘
              已完成  │      │  作废
                    ┌─▼──┐  ┌─▼──┐
                    │已完成│  │作废│  ← 终态（不可再改）
                    └─────┘  └────┘
```

**关键差异**：
- 代码允许从「草案」「已确认」「部分执行」任一状态直接跳到「作废」
- 终态「已完成」和「作废」不可再流转
- 转卡（convert）要求状态为「已确认」或「部分执行」，成功后自动推进到「部分执行」

### 3.3 前端状态流转（plansPage.js）

前端 `STATE_FLOW` 与后端 `_TRANSITIONS` **一致**——两端都硬编码了相同的白名单：
```js
const STATE_FLOW = {
  '草案': ['已确认', '作废'],
  '已确认': ['部分执行', '作废'],
  '部分执行': ['已完成', '作废'],
  '已完成': [],
  '作废': [],
};
```

### 3.4 状态机完整性评估

| 检查项 | 结果 |
|--------|------|
| 死状态 | **无**。所有五态均可到达 |
| 不可达状态 | **无** |
| 终态保护 | **有**。已完成/作废不可再流转 |
| 转卡前置条件 | **有**。仅已确认/部分执行可转 |
| 自动推进 | **部分**。转卡自动推进到「部分执行」，但「已完成」需人工手动改 |

---

## 四、并发安全问题清单

### 4.1 🔴 P0：`_next_num()` 无并发保护

**文件**：`server/board/plans.py:223-236`

```python
def _next_num(repo_root: Path, prefix: str) -> str:
    plans_dir = repo_root / "docs" / "projects" / prefix / "plans"
    if not plans_dir.exists():
        return "001"
    max_n = 0
    for f in plans_dir.glob("[0-9][0-9][0-9]-*.md"):
        try:
            n = int(f.name[:3])
            if n > max_n:
                max_n = n
        except ValueError:
            continue
    return f"{max_n + 1:03d}"
```

**问题**：无任何锁保护。两个并发 `POST /plans/create` 请求会得到相同的编号，导致第二个请求的文件覆盖第一个。

**严重程度**：`ThreadingHTTPServer` 是多线程并发，两个请求同时 `mkdir` + `write_text` 时第二个直接覆盖第一个（无 `exist_ok=False` 检查）。

**修复建议**：在 `create_plan` 中加锁（与 `convert_plan` 共用 `_acquire_convert_lock`），或使用 `open(..., 'x')` 独占创建。

### 4.2 🟡 P1：`_next_num` 与 `plan_reservations` 的编号空间不一致

`_next_num` 只看已存在的方案文件，不看 `plan_reservations` 保留的编号。但 `plan_reservations.py` 中的 `next_free_card_id()` 同时检查已存在卡和方案保留。方案侧缺少类似的统一保留逻辑。

### 4.3 🟢 P2：`convert_plan` 并发锁覆盖良好

`_acquire_convert_lock` 有双层保护：
1. `fcntl.flock`（文件锁，多进程安全）
2. `threading.Lock`（fcntl 不可用时的退路）

同一个前缀同时只允许一个转卡，防重复出卡。**设计良好**。

### 4.4 🟡 P1：`update_plan` 读写竞争

`update_plan` 先读文件（`read_text`），修改后写回（`write_text`），中间无锁。两个并发更新会丢失其中一个的修改。

**影响**：低概率（状态更新通常不频繁），但存在。

### 4.5 🟡 P1：`create_plan` 文件写入无原子性

```python
file_path.write_text(plan_content)  # 直接写盘
# 然后校验...
if result.returncode != 0:
    file_path.unlink(missing_ok=True)  # 校验失败删文件
```

从写入到校验之间有一个窗口，文件已存在但可能被覆盖。如果并发场景下两个请求写入同一个文件，校验可能基于混合内容。

---

## 五、死代码/冗余代码清单

### 5.1 未使用的端点

| 代码 | 位置 | 说明 |
|------|------|------|
| `roadmap_aggregate()` | `queries.py:94-96` | 仅包装 `roadmap_overview()`，无调用方 |
| `roadmap_project_detail()` | `queries.py:142-159` | 服务端路由使用 `roadmap_parser.py` 的同名函数，而非 `queries.py` 中的版本 |
| `/board/roadmap/by_project` | 无路由 | 头部文档未提及，代码中也无路由 |

### 5.2 头部文档遗漏

`server.py` 第 19-27 行的 API 文档列表遗漏了：
- `GET /plans/card-states`（第 1995-2005 行实际存在）
- `GET /board/roadmap/<project>`（第 2765-2787 行实际存在）

### 5.3 语义重复

- `plans.py:_extract_header_fields` 和 `loader.py:_parse_metadata` 都在做 Markdown 头部解析，但实现不同（一个用 `·` 分割，一个用 key-value 解析）
- `roadmap_parser.py:normalize_state` 与 `observer` 模块中的同名函数语义重复（roadmap_parser 注释中已标注）

### 5.4 硬编码

- `plans.py:28` `VALID_STATES` 硬编码五态（与 `models.py:STATES` 不同——后者是卡的五态，前者是方案的五态，语义不同但值部分重叠）
- `plansPage.js:18` 前端同样硬编码五态，两端需同步维护

---

## 六、认证/权限控制

### 6.1 鉴权流程

```
请求 → path 在 _NO_AUTH_PATHS? → 是 → 放行
         ↓ 否
      _auth_required()? → 否 (CCC_WEB_AUTH_REQUIRED=0) → 放行
         ↓ 是
      Authorization: Bearer <token>? → 否 → 401
         ↓ 是
      token 有效? → 否 → 401
         ↓ 是
      放行
```

### 6.2 Plans 端点鉴权

| 端点 | 鉴权 | 免鉴权白名单 |
|------|------|-------------|
| GET /plans/list | ✅ 需要 | ❌ 不在 `_NO_AUTH_PATHS` |
| GET /plans/card-states | ✅ 需要 | ❌ |
| GET /plans/detail | ✅ 需要 | ❌ |
| POST /plans/create | ✅ 需要 | ❌ |
| POST /plans/update | ✅ 需要 | ❌ |
| POST /plans/convert | ✅ 需要 | ❌ |

**注意**：默认 `CCC_WEB_AUTH_REQUIRED=0`（免登录模式），所有端点实际放行。仅在显式设置 `=1` 后生效。

### 6.3 权限控制缺失

- **无项目级权限**：任何有 token 的用户可以操作任意项目的方案
- **无角色区分**：创建/更新/转卡无权限分级（中枢席 vs 执行体）
- **转卡操作无二次确认**（前端有 confirm，但后端无）

---

## 七、错误处理完整性

### 7.1 各端点错误处理

| 端点 | 缺少参数 | 文件不存在 | 系统错误 | 业务规则 |
|------|---------|-----------|---------|---------|
| list | ✅ 容错（空列表） | ✅ 目录不存在返回空 | ✅ OSError → 500 | ✅ |
| detail | ✅ 400 | ✅ 404 | ✅ 500 | ✅ |
| create | ✅ 400 | N/A | ✅ 校验失败回滚 | ✅ 前缀校验 |
| update | ✅ 400 | ✅ 文件不存在 | ✅ 读取失败 | ✅ 状态流转白名单 |
| convert | ✅ 400 | ✅ 文件不存在 | ✅ 锁/子进程失败 | ✅ 状态检查/禁出卡前缀 |
| card-states | ✅ 容错 | ✅ | ✅ 500 | ✅ |

### 7.2 错误处理遗漏

1. **create_plan**：校验失败后 `unlink(missing_ok=True)` 只删文件，不清理 `plans/` 目录（如果这是第一个文件，空目录残留）
2. **convert_plan**：git push 失败后返回 `partial: true`，但文件已修改、卡已落盘，无自动重试或回滚
3. **get_plan / list_plans**：`plan_file.read_text()` 异常被静默跳过（`continue`），不记录日志

---

## 八、与 qx2 分析的交叉验证

### 8.1 验证通过的点

| qx2 结论 | 验证结果 | 证据 |
|----------|---------|------|
| Plan 实体模型描述 | ✅ 正确 | `plans.py:47-220` 字段提取与 qx2 描述一致 |
| 状态机五态定义 | ✅ 正确 | `plans.py:28 VALID_STATES` |
| 转卡时自动推进状态为「部分执行」 | ✅ 正确 | `plans.py:623` |
| 转卡时并发锁（fcntl） | ✅ 正确 | `plans.py:397-438` |
| 方案"已完成"依赖人工回写 | ✅ 正确 | 无自动推进到「已完成」的逻辑 |
| 转卡计划解析按行分割 | ✅ 正确 | `plans.py:583-590` 逐行 split |
| Git push 失败后 partial 状态 | ✅ 正确 | `plans.py:663-669` |

### 8.2 需要修正的点

| qx2 结论 | 实际情况 | 修正 |
|----------|---------|------|
| 状态流转为线性 `草案→已确认→部分执行→已完成→作废` | 代码允许从「草案」「已确认」「部分执行」任一状态直接跳到「作废」 | qx2 引用了 DOC-PROTOCOL 的文档描述，但遗漏了代码实现中「作废」是多源可达的 |
| `roadmap.md` 未被后端完全数据化 | `roadmap_parser.py` 已实现完整的结构化解析（`parse_business_lines` + `attach_card_states` + `project_detail`），前端已渲染图形化线路图 | qx2 分析可能基于旧版本代码 |
| 数据流图中 `cards.index.jsonl` 被描述为 cache | 实际是 `load_dispatch_cards` 生成的增量索引文件，与 `plans.py` 无直接关系；`plans.py` 直接读文件系统 | 索引文件路径正确，但不在 plans 数据流中 |
| 建议新增 `GET /plans/convert-preview` | 前端 `doConvert` 已通过 `GET /plans/detail` 读取「转卡计划」段并做行数校验和确认 | 预览功能已存在（通过 detail 接口），专门接口价值有限 |

### 8.3 qx2 遗漏的关键问题

| 问题 | 严重程度 | qx2 是否覆盖 |
|------|---------|-------------|
| `_next_num()` 无并发保护 | 🔴 P0 | ❌ 未覆盖 |
| `update_plan` 读写竞争 | 🟡 P1 | ❌ 未覆盖 |
| `create_plan` 文件写入无原子性 | 🟡 P1 | ❌ 未覆盖 |
| `/plans/card-states` 未在头部文档列出 | 🟢 P2 | ❌ 未覆盖 |
| `queries.py` 中 `roadmap_aggregate` / `roadmap_project_detail` 死代码 | 🟢 P2 | ❌ 未覆盖 |
| 前端/后端 `STATE_FLOW` / `_TRANSITIONS` 硬编码同步维护 | 🟢 P2 | ❌ 未覆盖 |
| 方案编号空间与卡编号空间的 `plan_reservations` 保护 | 🟡 P1 | ❌ 未覆盖 |

---

## 九、前端数据流

### 9.1 计划页（#/plans）

```
mountPlans()
  ├─ apiGet('/projects')          → 项目列表（供筛选下拉）
  ├─ apiGet('/cards?page_size=500') → 卡状态（供关联卡徽章）
  ├─ apiGet('/plans/list')        → 方案列表
  ├─ apiGet('/plans/card-states') → 流程条数据（六列分布）
  └─ setInterval(30s)              → 自动刷新
```

### 9.2 线路图页（#/roadmap）

```
mountRoadmap()
  └─ apiGet('/board/roadmap')     → {overview, by_project, business_lines}
       └─ 点击项目卡片
            └─ apiGet('/board/roadmap/<project>') → 单项目详情
                 ├─ buildTimelineOverview()  → 总览条
                 ├─ buildMilestoneRail()    → 左垂直时间线
                 ├─ milestonePanelHTML()    → 右卡面板（按状态分组）
                 └─ riskHTML()              → 底部风险
```

### 9.3 拖拽改状态（plansPage.js）

前端 `doMoveCard` 有本地 `STATE_FLOW` 白名单预判，后端 `update_plan` 有 `_TRANSITIONS` 兜底。两端需同步维护。

---

## 十、总结

### 架构质量评分

| 维度 | 评分 | 说明 |
|------|------|------|
| API 设计 | 85/100 | 端点清晰，RESTful 风格，缺少 `/plans/card-states` 文档 |
| 数据模型 | 80/100 | 文件即数据库，简单可靠；字段提取依赖正则，脆弱 |
| 状态机 | 85/100 | 白名单流转，终态保护；前端后端需同步维护 |
| 并发安全 | 60/100 | convert 有锁，但 create 和 update 无保护 |
| 错误处理 | 75/100 | 主要路径覆盖，缺 partial 状态的恢复机制 |
| 前端体验 | 85/100 | 流程条、拖拽改状态、图形化线路图均已完成 |

### 优先修复项

1. **P0**：`_next_num()` 加并发锁，防止编号重复
2. **P1**：`create_plan` 文件写入加原子性保护（`open('x')` 或锁）
3. **P1**：`update_plan` 加读写锁
4. **P2**：`server.py` 头部文档补全 `/plans/card-states` 和 `/board/roadmap/<project>`
5. **P2**：清理 `queries.py` 中的死代码（`roadmap_aggregate`、`roadmap_project_detail`）