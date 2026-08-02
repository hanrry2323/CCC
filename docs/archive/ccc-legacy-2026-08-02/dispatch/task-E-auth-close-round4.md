# 任务书 E · 鉴权收口：Basic 弱口令降级为可选开关（窗口 1）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 1 即可。  
> 前提：B2（后端会话 token）+ A3（前端登录）已合入 main。本任务收掉「Basic 弱口令仍是 operator 全权」的尾巴。

## 0. 先读

1. `CLAUDE.md`
2. `docs/dispatch/report-B2-backend-auth-round2.md`（鉴权现状与契约）
3. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 任务目标

1. **后端开关**：新增 `CCC_AUTH_REQUIRE_BEARER`（默认 off）——on：拒绝 Basic（仅 Bearer，401）；off：现行为（Basic 兼容 + 迁移告警日志）
2. **兼容保护**：Desktop / sidecar / 工具链的 Basic 调用在默认态不受影响；文档写清两态行为与迁移路径
3. **前端确认**：A3 登录流在 REQUIRED 模式下可用（无 token → 登录视图；401 → 引导重登）；扫前端确认无硬编码 Basic 残留
4. **测试**：鉴权用例扩展覆盖两态（on：Basic 401 / Bearer 通过；off：Basic 兼容）

## 2. 允许范围

- `scripts/chat_server/auth.py` 与相关后端鉴权逻辑、`scripts/chat_server/routers/auth.py`、相关测试
- 与开关说明相关的 docs（GO-LIVE / hub 文档，变更列入报告）
- 前端仅允许「无残留确认」类改动（不引入新 UI）

## 3. 红线（禁止）

- **默认态不得改变现有行为**（开关 off = 现在的一切）；不打断 Desktop/sidecar 链路
- 不引入密钥/真实凭据入库；token 只进 sessionStorage（前端既有约定）
- 4000/4100 relay 相关、DRY_RUN 类保护、产线启动
- 提交 main

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「开关设计 + 两态影响面 + 迁移路径」，**不写代码**。  
确认后实现，两态测试全绿再提交。

## 5. 验收标准

- `CCC_AUTH_REQUIRE_BEARER=1`：Basic 请求 401（有测试）；Bearer 正常
- 默认态：Basic 兼容，全量既有鉴权测试绿
- 前端无 Basic 硬编码残留（有结构锁或 grep 证据）
- 文档两态说明与实现一致
- 提交在 `codex/ws-5-auth-close` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 移交项（如需后续窗口配合）
