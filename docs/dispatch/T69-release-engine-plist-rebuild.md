# 任务卡 T69 · release.sh Engine plist 自愈（T68 部署事故修复）

> 关联：T68 部署事故（2026-08-05：start_engine 遇 plist 缺失仅 WARN，Engine 掉线未恢复，Codex 现场重建恢复）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：请先创建独立 worktree `git -C /Users/fan/program/CCC worktree add /Users/fan/program/ccc-dev-ws-t69 -b codex/t69-release-engine-plist-rebuild origin/main`；分支 `codex/t69-release-engine-plist-rebuild`
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

`deploy/release.sh` 的 `start_engine()` 在 `~/Library/LaunchAgents/com.ccc.engine.plist` 缺失时，能从仓库模板 `server/deploy/com.ccc.engine.plist` 自动重建并恢复服务；重建不可行时明确 FAIL 阻止部署（不再静默掉 Engine）。

## 背景（事故复盘）

2026-08-05 T68 部署时：`stop_engine()` bootout 成功 → `start_engine()` 检测到 plist 缺失 → 只打 WARN「服务未注册/plist 缺失」继续 → Engine 掉线，/health、/board 验证失败，脚本还在 CONV_RESULT 处崩溃。Codex 现场从仓库模板重建 plist（解析 $PROJECT_ROOT/$CONFIG_ENV/$DATA_DIR/$LOG_DIR/$USERNAME）后 bootstrap 恢复。根因：start_engine 对 plist 缺失无重建能力，且失败仅 WARN 不阻断。

## 具体项

1. **plist 自愈**：`start_engine()` 在 `launchctl print` 失败且 plist 文件缺失时，从 `$REPO_PATH/server/deploy/com.ccc.engine.plist` 模板解析占位符（`$PROJECT_ROOT`→`$REPO_PATH`、`$ENGINE_ENTRY`→`.venv-hub/bin/python -m server.engine.main`、`$CONFIG_ENV`→`$REPO_PATH/server/config/config.env`、`$DATA_DIR`→`$REPO_PATH/data` 或 `CCC_DATA_DIR`、`$LOG_DIR`→`$LOG_DIR`（config.env 的 EXECUTOR_LOG_DIR 同级目录或 ~/.ccc/logs）、`$USERNAME`→当前用户）生成到 `$HOME/Library/LaunchAgents/com.ccc.engine.plist`，再 `launchctl bootstrap`。
2. **失败必须阻断**：模板缺失 / 解析失败 / bootstrap 失败 → `record FAIL` 且部署终止（exit 1），不再 WARN 继续。
3. **部署后自检**：checkout + kickstart 后加一步 `launchctl list | grep com.ccc.engine` + Engine 心跳日志非空校验，确认 Engine 真的在跑（防「服务未注册但脚本继续」）。
4. **顺带排查 plist 消失根因**：查 2017 上 com.ccc.engine.plist 文件历史（ls 时间 / shell 历史 / 是否有操作删除），把结论写回回写区（无结论就明确写「未定位，靠自愈兜底」）。
5. 回归：正常路径（plist 在）走 kickstart 分支行为不变；`--simulate` 全过。

## 红线

1. 只改 `deploy/release.sh` + `server/tests/`（或新增 release 测试脚本）；**禁止改 server/engine/web 逻辑**。
2. 不改变 T67 已落地的 stop_engine/在途等待逻辑；只增强 start_engine 与收尾自检。
3. 回写前 push 成功并附证据。

## 验收标准

1. 模拟 plist 缺失（测试环境：临时 HOME 或 mock launchctl）→ start_engine 自动重建 + bootstrap 成功；模板缺失 → FAIL 阻断。
2. 正常路径回归：`bash -n`、`--simulate` 通过；release.sh 既有行为不变。
3. 部署后自检步骤存在且逻辑正确（代码审查）。
4. pytest 全绿（2017）、ruff 零告警、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：自愈实现、模拟测试证据、plist 消失根因排查结论、回归结果、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
