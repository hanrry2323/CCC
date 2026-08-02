# 任务书 H · Basic 调用方迁移（desktop 侧）→ Bearer（窗口 2）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 2 即可。  
> 前提：`CCC_AUTH_REQUIRE_BEARER` 开关已合入（默认 off）；`APIClient.swift` 已有部分 Bearer 路径（197 行），Basic 残留在统一入口（379 行附近）。本窗口把桌面端收敛到 Bearer。

## 0. 先读

1. `CLAUDE.md`
2. `desktop/Sources/CCCDesktop/APIClient.swift`、`AppModel.swift` 现有认证路径
3. `docs/dispatch/report-B2-backend-auth-round2.md`（鉴权契约，含 `/api/auth/token`）
4. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 任务目标

1. **统一认证**：桌面端所有 Hub 请求统一走 Bearer；Basic 仅在换取 token 时出现一次（启动/登录时 `POST /api/auth/token`）
2. **token 生命周期**：内存缓存 + TTL 前刷新；401 → 重取一次 → 仍失败再报错（不无限循环、不白屏）
3. **配置**：Hub 账号密码来源保持现有配置机制，代码内不新增硬编码凭据；明确降级策略（开关 off 期间不断链）
4. **测试**：在已有桌面端测试基建上补 token 获取/刷新/401 重取行为锁

## 2. 允许范围

- `desktop/`（Swift）全部相关文件、`desktop/Tests/`、与构建/测试相关的配置

## 3. 红线（禁止）

- `scripts/`（归窗口 1）、服务端鉴权逻辑
- 凭据硬编码入库；不启动产线；不改 DRY_RUN
- release 构建必须通过；桌面端对话/转任务链路不得破坏
- 提交 main

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「认证收敛方案 + token 生命周期 + 降级策略 + 测试清单」，**不写代码**。  
确认后实现，`swift test` 全绿 + release 构建通过再提交。

## 5. 验收标准

- `rg` 证明 desktop 无硬编码 Basic 头残留（白名单：token 换取处）
- token 缓存/刷新/401 重取有测试覆盖
- `swift test` 全绿；`swift build -c release` 通过
- 提交在 `codex/ws-6-desktop-bearer` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 移交项（与窗口 1 的衔接点）
