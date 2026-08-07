# 任务卡 hp005 · 前端治理：假数据边界与API契约三方对齐（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-07

## 目标

治理 HP Dashboard 前端的两个根问题（此前侦察确认）：① 假数据越界（后端在线也渲染硬编码数字/假文档，各页 fallback 互不一致）；② API 契约三方漂移（api.ts ↔ server.py ↔ API_CONTRACT.md，含假按钮与无效筛选）。

## 红线（先看）

1. **只动前端面**：`local/graph/dashboard/`（src + 配置）与 `local/graph/server.py`、`local/graph/API_CONTRACT.md`。**禁止**动 DB 数据、采集链路（kb-collect/ingest，归 hp004）、检索逻辑（kb-search，归 hp006）。
2. 行为契约：前端改动必须同时更新 `API_CONTRACT.md`（三方同步是 K12 确立的契约优先原则）；未定义的端点不得新增。
3. 假数据治理方式：**真数据缺失时显示真实空态/错误态**（去掉硬编码数字与假文档填充），禁止继续用「空则替」假数据掩盖失败。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `local/graph/dashboard/src/`（api.ts、store.ts、pages/、components/、utils/）
- `local/graph/server.py`（BaseHTTPRequestHandler :8089）
- `local/graph/API_CONTRACT.md`
- dashboard 测试（api.test.ts / vitest，随改随测）

## 步骤

1. 读三份现状：`src/api.ts`、`server.py`、`API_CONTRACT.md`，列出三方差异清单（已知项：`/api/search` 的 mode 参数后端忽略、`status=draft` 筛选无效、`/api/quality` 未入契约、CORS 方法表缺 DELETE、chunks schema 缺 domain/node_type 列）。
2. **契约优先**：以 API_CONTRACT.md 为基准，决定每个漂移点「修契约 or 修代码」：
   - 有效意图（mode 搜索模式、draft 筛选）→ 后端补齐实现 + 契约补定义
   - 无效/过度设计（假模式按钮等）→ 前端去掉入口 + 契约对齐
   - 缺失项（quality、CORS DELETE）→ 契约补录 + 代码对齐
3. **假数据治理**：
   - 删各页 FALLBACK_* 硬编码假数据（约 250 行，Dashboard/Library/Search/Document/Notes/Activity 六处）；后端不可达 → 显示真实错误态（已有横幅机制）+ 空数据，禁止假数字（1,247/38/7 等）与假文档
   - 统一数据获取模式（提取共用 fetch hook 或至少统一空态/加载态组件，消除 6 份互不一致的实现）
4. 修真实 bug：`?doc_id=` 双斜杠前缀（server.py:816）导致笔记保存后列表清空；Document 404 渲染空白（降级不一致）；搜索竞态（加请求序号/AbortController）；note-saved 事件无人监听（Notes 保存后刷新）。
5. 死 UI 治理：Library 排序/筛选/密度、Search 分组/tab/分页、Sidebar 死链接——要么实现要么移除入口（按步骤 2 的「有效意图」判定）。
6. 测试：`cd local/graph/dashboard && pnpm test`（vitest）全绿；`python3 -m pytest`（server 侧 tests/，若 server.py 有对应测试）全绿。
7. 探针实测：Dashboard 前端可访问（:8090），后端停掉时页面显示错误态而非假数据（可临时停 :8089 验证后恢复——注意与机审/他卡错开，避免影响运行）。
8. commit+push 到卡内分支 `codex/hp005-frontend-fake-data-contract`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」。
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 三方契约对齐：API_CONTRACT.md 与 server.py、api.ts 逐端点核对一致（回写区附核对表）；`mode`、`draft`、`quality`、CORS 四项漂移全部闭环。
2. 假数据清零：源码 grep 无 FALLBACK_ 硬编码假数据/假数字；后端不可达时页面渲染错误态（实测截图或 curl 证据）。
3. 已知 bug 修复有测试：笔记保存刷新、404 降级、搜索竞态三处各有 vitest 用例或实测证据。
4. `pnpm test` 全绿；server 侧 pytest（如有）全绿。
5. 前端功能不回归：:8090 页面可访问、搜索/库/笔记主流程可用。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
