# Brief F4-3 · Proactive 触发（CI 失败 / git hook → backlog bug epic）

| 字段 | 值 |
|------|-----|
| brief_id | `F4-20260721-proactive-triggers` |
| 波次 | F4 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | 流畅基线已达成；F4-1/F4-2 可并行（不互相依赖） |
| 模型提示 | **编排窗用高级模型**（涉及外部信号入队 + 边界） |

## 1. 目标

让外部信号（CI 失败 / git hook）能**自动投递** backlog bug epic 到指定业务仓，进队后走既有 Engine 流水线。补 Loop Engineering 的 Proactive 触发档。

## 2. 非目标

- 不接 CI 平台 API（先做「接收 payload」入口；CI 侧 webhook 后配）  
- 不自动部署 / 不自动重跑 CI  
- 不改 Engine 主循环 / 不改 transfer/flow 字段  
- 不改 Desktop / SSE  
- 不让人批进入流水线（仍是意图门 = 投递即受理）  
- 不处理 spam / 鉴权绕过（先内网；Basic Auth 复用）  

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| hub-api-v1 | **有小补** | 新 `POST /api/desktop/proactive-epic`（或复用 transfer + `source=proactive` 标记）；先改 `hub-api-v1.md` |
| flow-events | 无 | 复用 `epic_created` |
| 其它 docs | 有 | `docs/product/proactive-triggers.md`（新） |

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| `POST /api/desktop/transfer`（人审意图门） | 无外部信号入队路径 |
| Engine 消费 backlog epic | 无 CI/hook → backlog 自动投递 |
| abnormal 止损（Phase9） | CI 失败不自动进队 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `scripts/chat_server/routers/desktop.py`（加 `POST /api/desktop/proactive-epic`）· `scripts/chat_server/app.py`（若需注册）· `scripts/ccc-ingest-ci-failure.sh`（新；CLI 入口）· `tests/scripts/test_proactive_epic.py`（新）· `docs/product/hub-api-v1.md`（先改）· `docs/product/proactive-triggers.md`（新）· 本 brief §8 | 改 Engine 主循环、改 Desktop、改 transfer 字段、改 flow-events |
| 过桥 | 按需 | 同上（编排与过桥可合一窗） | |
| 壳 | 否 | — | |
| 架构 | 验收 | 本 brief · `hub-api-v1` 审阅 | 代写实现 |

## 6. 行为规格

1. 新端点 `POST /api/desktop/proactive-epic`：  
   - Body：`{project_id, source: "ci"|"git_hook"|"external", title, goal, acceptance?, payload?}`  
   - 鉴权：复用 Basic Auth  
   - 行为：等价 transfer（进 backlog epic；`executor_intent="bug"`；`client_request_id` 幂等键由 `source + payload.hash` 生成）  
   - 响应：`{ok, epic_id, queued: true}`；不调 Engine wake（Engine tick 自取）  
2. `scripts/ccc-ingest-ci-failure.sh`：CLI 包装，从 stdin / 文件读 CI 失败 JSON → POST 端点。  
3. `hub-api-v1.md` 先改：加端点行 + 字段表 + 「Proactive = 意图门外的自动意图，仍走 backlog」。  
4. `proactive-triggers.md`：用法 + CI webhook 配置示例 + 鉴权提醒。  
5. 不双投：若 `client_request_id` 已存在 → 返回已有 epic（幂等）。  

## 7. 验收清单

- [x] `hub-api-v1.md` 先改（端点 + 字段）
- [x] `POST /api/desktop/proactive-epic` 实现；幂等
- [x] `ccc-ingest-ci-failure.sh` CLI 绿
- [x] `proactive-triggers.md` 落地
- [x] `tests/scripts/test_proactive_epic.py` 绿（投递 + 幂等 + 鉴权失败 401）
- [x] `pytest tests/scripts/ -q` 仍绿
- [x] 白名单外无改动

## 8. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 编排 | `POST /api/desktop/proactive-epic`（bug epic、幂等 CRID、不 wake）；`ccc-ingest-ci-failure.sh`；hub-api-v1 §3b + proactive-triggers.md | `test_proactive_epic` 绿；`pytest tests/scripts/ -q` 绿 | 是 |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | （待填） |
| 缺口 | |
| 验收日 | |
