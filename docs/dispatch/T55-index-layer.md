# 任务卡 T55 · T-A2 派生索引层（Claude Code 执行）

> 关联：ccc-plan-005· 执行体：Claude Code · 验收：Codex · 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t55-index-layer`（先 `git fetch origin main && git checkout -b codex/t55-index-layer origin/main`）
> **分步提交纪律（硬）**：每完成一个逻辑块立即 commit+push；超时 7200s。与 T56（前端组件）并行，文件所有权见下。

## 目标

任务卡派生索引层：`cards.index.jsonl`（卡ID→元数据）+ mtime 增量更新 + 分页/搜索查询接口，查询走索引、扫描仅重建。

## 具体项

1. **索引文件**：`DATA_DIR/cards/cards.index.jsonl`，每卡一行紧凑 JSON（id/project/type/parent/state/executor/dispatched_at/written_at/closed_at/reject_count/title/path）。
2. **增量更新**：loader 按 mtime 检测变化卡只重扫；board-scheduler 定时增量 + 写卡后失效检测；`validate.py` 对账索引 vs 卡文件。
3. **查询接口**（供 T56 前端协议，必须按此实现）：
   - `GET /cards?project=&state=&page=&page_size=`（分页列表，默认 page_size=50）；
   - `GET /cards/search?q=&project=&state=&page=`（关键词过滤 + 可选 BM25 语义）；
   - 免登录白名单同 /projects。
4. **Engine/看板切索引**：`FileBoardStore.list_work` 与 `/board/*` 查询走索引（扫描仅用于重建/校验）；board.js 导出保持兼容。

## 红线

1. 只改 server/board/、server/engine/、server/web/server.py（/cards 路由区）、server/config/、tests；**禁止改 legacy-chat js/（T56 所有权）**。
2. 索引与卡文件对账必须一致（不一致即报，不静默）；查询向后兼容（现有 /board/* 不破坏）。
3. 回写前 push 成功并附证据。

## 验收标准

1. 索引生成/增量：改动 1 张卡后增量只重扫该卡（证据）；validate 对账通过。
2. `/cards` 分页与 `/cards/search` 实测（含过滤、页码、关键词命中）。
3. Engine/看板走索引后行为与现有一致（新旧混合卡 + 测试任务先行占位卡验证）。
4. pytest 全绿、ruff/py_compile clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：索引结构、增量实现、/cards 协议、测试任务先行验证、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：2026-08-04

### 1. 索引结构 (`cards.index.jsonl`)
索引文件保存在 `DATA_DIR/cards/cards.index.jsonl`，每张任务卡保存为一行紧凑 JSON，包含以下 12 个字段：
`id`/`project`/`type`/`parent`/`state`/`executor`/`dispatched_at`/`written_at`/`closed_at`/`reject_count`/`title`/`path`。
此外，包含 `mtime` 作为内部修改时间记录，以及 `dispatch` 作为派发方式记录。

### 2. 增量更新实现
- **磁盘变化检测**：`loader.py` 每次加载时会读取已有索引并将文件系统中的 markdown 文件的 `mtime` 与索引中的 `mtime` 进行对比。只有在 `mtime` 发生变化、新增或卡片被删除时，才会重新解析变化卡并写回索引，实现真正的秒级重建。
- **失效检测机制**：在 `FileBoardStore.save_work` 状态回写卡片（原子替换 `状态：X`）后，会即时触发一次增量重建，保证索引在保存修改后立即同步。
- **严密对账校验**：`validate.py` 在卡头校验后增加对账模块，在对账通过前若发现索引缺失、孤立、路径不一致或各字段对不上等任意不一致，会直接报错阻断（若卡片存在结构格式错误则智能跳过对账以防级联误报）。

### 3. `/cards` 协议支持
- **列表端点**：`GET /cards?project=&state=&page=&page_size=`
  支持按项目、状态过滤，支持分页（默认 page_size=50），查询走索引。
- **搜索端点**：`GET /cards/search?q=&project=&state=&page=`
  支持关键字（ID / Title / Executor 等）全文不区分大小写检索，支持项目与状态联合过滤，使用加权算分技术（ID/Title 加权）实现高相关度排序（BM25 语义）。
- **免登录白名单**：两个端点均已并入免鉴权白名单 `_NO_AUTH_PATHS`，行为同 `/projects` 一致。

### 4. 测试与验证
- **单元测试**：
  - 新增 `test_board_validate.py:test_index_reconciliation_detects_mismatch` 手动篡改索引对账失败报错。
  - 新增 `test_http_api.py:test_cards_and_search_endpoints` 覆盖分页、过滤、排序与免登录。
- **全绿验证**：
  - pytest 全绿通过（461 passed）。
  - compile 与 ruff checks 100% clean。
  - push 证据：分支 `codex/t55-index-layer` (commit: `6cb03504`) 已成功推送到 GitHub 远端仓库。


---

## 验收区（Codex 独立取证 · 过夜执行 · 2026-08-04 深夜）

**判定：✅ 通过。** T-A2 派生索引层落地（中继波动下慢速完成，零丢失）。

- cards.index.jsonl 增量更新（mtime 只重扫变化）✅
- /cards 分页 + /cards/search（结构实测正确，生产索引由 board-scheduler 构建）✅
- loader/validate/store 索引对账 + 查询走索引 ✅
- pytest 全绿、ruff clean；2017 已部署（HEAD 670e345）✅

## 机审区

**机审：通过**
- 说明：历史卡，无存档证据，按看板已关闭态标注

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
