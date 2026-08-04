# 任务卡 T55 · T-A2 派生索引层（Claude Code 执行）

> 关联：阶段 3（T-A2 索引层，过夜任务后端链 1/3）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-04
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

**执行体**：Claude Code（2017）· 日期：
