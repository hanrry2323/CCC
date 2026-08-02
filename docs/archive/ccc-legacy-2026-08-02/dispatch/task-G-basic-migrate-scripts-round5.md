# 任务书 G · Basic 调用方迁移（scripts 侧）→ Bearer（窗口 1）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 1 即可。  
> 前提：`CCC_AUTH_REQUIRE_BEARER` 开关已合入（默认 off）。要真正开 on，所有 Basic 调用方必须先行迁 Bearer。本窗口负责 scripts/ 侧。

## 0. 先读

1. `CLAUDE.md`
2. `docs/dispatch/report-B2-backend-auth-round2.md`（鉴权契约）、`docs/ops/GO-LIVE.md`（两态说明）
3. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 任务目标

1. **公共认证辅助**：新建统一模块（如 `scripts/_hub_auth.py`）——`POST /api/auth/token`（Basic 换 Bearer）、内存缓存 + TTL 前刷新、401 重取、失败降级策略明确（开关 off 期间也不断链）
2. **迁移 Basic 调用方**（至少）：
   - `scripts/ccc-hub-lens.py`、`verify-ccc-hub.py`、`ccc-mind-update.py`、`ccc-submit-proposal.py`、`ccc-stress-matrix.py`
   - `scripts/smoke-hub-empty-transfer-retry.sh`、`smoke-desktop-stable.sh`、`ccc-hub-probe.sh`
   - `scripts/chat_server/services/hub_agent_tools.py`、`transfer_outbox_flush.py`、`_ccc_control.py`
3. 每个脚本迁移后功能等价（读/写权限不变）；统一走辅助模块，不各自造轮子
4. 文档：迁移清单更新（GO-LIVE 两态小节补「已迁移调用方」）

## 2. 允许范围

- `scripts/` 下工具/服务脚本与测试、相关 docs

## 3. 红线（禁止）

- **服务端鉴权逻辑不动**（`auth.py`、`routers/auth.py`、`config.py` 只读）；`desktop/` 归窗口 2
- 凭据不入库；不启动产线；不改 DRY_RUN
- 开关 on 之前不得破坏现有链路（默认态回归必须绿）
- 提交 main

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「辅助模块设计 + 调用方清单 + 每处迁移点与降级策略」，**不写代码**。  
确认后实现，测试全绿再提交。

## 5. 验收标准

- `rg` 证明脚本侧无硬编码 Basic 头残留（白名单：服务端 token 登录口/开关实现）
- 辅助模块测试绿（缓存、TTL 刷新、401 重取、降级）
- 迁移脚本冒烟通过（现有测试/自检不新增失败）
- 提交在 `codex/ws-5-auth-migrate` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 移交项（桌面端配合项列给窗口 2）
