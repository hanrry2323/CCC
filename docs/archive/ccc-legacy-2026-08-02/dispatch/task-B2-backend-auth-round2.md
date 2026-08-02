# 任务书 B2 · 网页鉴权整改 + 遗留收尾（窗口 B 第二波）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 B 即可。  
> 前提：第一波（`task-B-backend-engine.md`）已实现并通过 Codex 审查后再接本任务书。

## 0. 先读

1. `CLAUDE.md`
2. 第一波完成报告（`docs/dispatch/report-B-backend-engine.md`）
3. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 背景（一句话）

网页看板/运维页现无真实鉴权：7788 默认无 Token，固定 Basic `ccc:ccc`，且 ops 日审 apply 可写业务仓——内网无鉴权风险已多次标记，本波收掉后端侧。

## 2. 任务目标

1. **后端鉴权**：为 `scripts/chat_server` 的 `/api/board`、`/api/ops/*` 加真实鉴权（会话 token 方案），写操作（apply / 日审 / 转任务）默认要求更高权限
2. **兼容过渡**：Desktop / sidecar 既有调用链路不破坏（现有 Basic 凭证需给出兼容或迁移路径，明确过渡期行为）
3. **遗留收尾**（第一波报告风险 2/3/4）：
   - `_executor.py` 长 prompt 死路径（仅 opencode-pool 用）：删或修，给出结论
   - `hygiene-python` patrol 卡标记改 `resolve_executor_from_skill` + `python`（对齐实际走向）
   - 文档漂移核对：CLAUDE.md 与 docs 中 `#/chat` 已删/跳转、看板「停更」等与现状不符的表述

## 3. 允许范围

- `scripts/chat_server/` 鉴权相关后端逻辑、`scripts/` 下 patrol/executor 收尾、相关测试
- 与鉴权过渡相关的 docs（变更列入报告）

## 4. 红线（禁止）

- **前端登录页/Token 存储不归本窗口**（窗口 A 配合，需衔接时在报告中列接口契约）
- 密钥/真实凭据入库；不改 DRY_RUN 类保护；不启动产线
- `desktop/`、`src-tauri/`、4000/4100 relay 相关
- 提交 main

## 5. 流程（spec-first 门）

第一轮：`/plan` 输出「鉴权方案（含兼容路径）+ 遗留三项的处理结论」，**不写代码**。  
确认后实现，测试全绿再提交。

## 6. 验收标准

- 写接口无有效凭证返回 401/403（有测试）
- Desktop / sidecar 正常流程回归通过（有证据）
- 遗留三项每条有结论（修了 / 暂缓 + 理由）
- 鉴权不引入密钥入库、不破坏现有 fail-open 之外的降级路径
- 提交在 `codex/ws-2-backend` 分支

## 7. 完成报告格式

发现 → 动作 → 证据 → 移交项（前端配合的单独列接口契约）
