# 任务卡 T8-X · 调用方切换执行（T4 阶段 4 放行）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1（§8 拓扑 / D9）
> 管理席/执行体：Claude Code（运行面，dispatch-sop 敏感运行面不派 Trae）· 验收：老板
> 状态：执行中 · 日期：2026-08-02 · 依据：老板放行 T8 执行
> 前置：T8 清单已验收；6100/6102 已部署运行（T4）

## 目标

CCC 执行体调用方从 M1 4100/4102 **切换**到 2017 6100/6102：Claude Code → 6100、OpenCode → 6102、Engine env → 6100。**M1 4100/4102 一根毫毛不动**；每步可回滚。

## 红线（先看）

1. **M1 4100/4102 零改动**：只改 2017 侧调用方指向，不碰 M1 中转站。
2. **先备份再改**：每个配置文件改前 `cp` 备份，失败即回滚。
3. **每步验证**：改完立即冒烟，不通过立即回滚该步。
4. 完成后 6100/6102 出模型响应；M1 4100/4102 仍正常（供 Codex 等未切换方使用）。
5. 未提交的配置改动不落 git（配置文件不进仓）。

## 步骤（Claude Code 执行）

### 0. 前置验证（不做不切）
1. `ssh fan@192.168.3.116` 确认 6100/6102 监听 + 双协议冒烟能出模型响应。

### 1. 备份（2017 侧）
2. `cp ~/.claude/settings.json ~/.claude/settings.json.bak-ccc-6100`
3. `cp ~/.config/opencode/opencode.json ~/.config/opencode/opencode.json.bak-ccc-6102`
4. `cp ~/.ccc/engine.env ~/.ccc/engine.env.bak-ccc-6100`（如存在）

### 2. 切换 Claude Code → 6100
5. 改 `~/.claude/settings.json` 的 `env.ANTHROPIC_BASE_URL` → `http://127.0.0.1:6100`
6. 验证：`ANTHROPIC_BASE_URL=http://127.0.0.1:6100 claude -p "respond OK"`（或 curl 6100）

### 3. 切换 OpenCode → 6102
7. 改 `~/.config/opencode/opencode.json` 的 `baseURL` → `http://127.0.0.1:6102/v1`
8. 验证：`opencode run --model loop/flash --auto --dir /tmp "respond OK"`（或 curl 6102）

### 4. 切换 Engine env → 6100/6102
9. 改 `~/.ccc/engine.env`：`AGENT_PLANNER_BASE_URL=http://127.0.0.1:6100`、`ANTHROPIC_BASE_URL=http://127.0.0.1:6100`
10. 重启 Engine：`launchctl kickstart gui/$(id -u)/com.ccc.engine`

### 5. 终验
11. 三调用方冒烟全过 + M1 4100/4102 仍监听（对比 PID 未变）

## 回滚（任何一步失败）
- Claude Code：`cp ~/.claude/settings.json.bak-ccc-6100 ~/.claude/settings.json`
- OpenCode：`cp ~/.config/opencode/opencode.json.bak-ccc-6102 ~/.config/opencode/opencode.json`
- Engine：`cp ~/.ccc/engine.env.bak-ccc-6100 ~/.ccc/engine.env` + 重启

## 验收标准（老板验收）

1. 6100/6102 冒烟通过（Anthropic + OpenAI Chat 均出模型响应）。
2. M1 4100/4102 监听不变（PID/端口对比）。
3. 所有配置有备份、可一键回滚。
4. M1 旧中转站**不停用**（D9 停用时机另定）。

## 回写区

（Claude Code 执行后回写）
