# 任务卡 T4 · CCC 自带中转站部署与调用方切换（Claude Code 执行）

> 关联：INT-120（D9 中转站并入）· 契约：CCC 重构契约 v1 · 管理席：Codex
> 执行体：Claude Code（CLI）· 验收：Codex · 状态：待分派 · 日期：2026-08-02
> 依赖：T1-R / T2 / T3（均已验收通过）
> 运行面提示：本卡默认只做「实现 + dry-run」；**实际部署到 2017 与调用方切换需老板放行后执行**（运行面动作；停用 M1 旧中转站的时机由老板定，D9）。

## 目标

把中转站（ai-loop-router）作为 CCC 基建配属落地：`server/relay/` 组件接线（配置化）+ 2017 部署脚本 + 三个调用方切换脚本（含备份与回滚）+ 健康检查。

## 红线（先看）

1. **不删除任何文件**；不碰旧代码；不碰控制面。
2. 密钥只占位（`$RELAY_UPSTREAM_KEY` 等），**不落盘任何明文令牌**。
3. **本卡默认不执行部署/切换**：只产脚本与 dry-run 输出；真实动作放行后由老板确认执行。脚本必须打印将执行的动作与回滚路径。
4. 验收标准不可自行解释；完成必须提交（真实 commit hash 回写）。
5. **切换必须有回滚方案**：新中转站不可用 → 自动/手动回指原地址；M1 旧实例保持可用，直至老板放行停用。

## 范围

- 新增：`server/relay/`（配置读取 / 健康检查桩 / 上游路由占位）、`server/deploy/` 中转站 plist 模板、`server/deploy/switch-relay.sh`（切换脚本，含 `--dry-run` 与 `--rollback`）。
- 修改：`server/config/config.example.env`（relay 段完善）。
- 不动：`server/engine/`、`server/board/`、`server/web/` 已验收部分（确需小改须在回写中说明）。

## 步骤

1. `server/relay/`：配置读取复用 `loader`；健康检查（`/health` 桩）；上游路由占位（中转站代码以独立仓部署，不重写）。
2. 2017 部署脚本：launchd plist 模板 + install/verify 脚本（`--dry-run` 只打印不执行）。
3. 切换脚本 `switch-relay.sh`：覆盖三个调用方——Claude Code（`~/.claude/settings.json` 的 `ANTHROPIC_BASE_URL`）、OpenCode（config `baseURL`）、Codex（config.toml 的 loop-router provider）；切换前备份原值；`--rollback` 还原。
4. 健康检查与验收命令：新中转站连通性测试脚本（HTTP 探活）。
5. 测试：脚本语法 + `--dry-run` 输出断言；配置校验；**无真实网络 / 部署动作**。
6. 提交 `chore(relay):`，回写真实 commit + 「待老板放行执行清单」（部署窗口 / 切换顺序 / 回滚路径）。

## 验收标准（Codex 按此验收）

1. `server/relay/` 接线完成，配置复用 loader，零硬编码。
2. 部署 / 切换 / 回滚脚本齐全，`--dry-run` 可安全运行并输出预期动作。
3. 调用方切换清单覆盖三处（Claude Code / OpenCode / Codex），含原值备份与回滚。
4. 测试与语法全绿；**无真实部署 / 切换动作发生**（本卡范围）。
5. 真实提交；工作树仅剩 2 个预存项；未碰旧代码 / 控制面 / 外脑。

## 回写要求

结果摘要（人话一句）、测试输出、dry-run 输出、commit hash、**待老板放行的执行清单**。

## 回写区

（Claude Code 回写）
