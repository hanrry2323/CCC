# 任务卡 T8-X · 调用方切换执行（T4 阶段 4 放行）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1（§8 拓扑 / D9）
> 执行体：Claude Code（管理席兼执行，运行面，dispatch-sop 敏感运行面不派 Trae）· 验收：老板 · 派发：manual · 项目：ccc
> 状态：已关闭 · 日期：2026-08-02 · 依据：老板放行 T8 执行；Codex 全面验收实测通过（6100/6102 运行、M1 未动）
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

**执行体**：Claude Code · 2026-08-02

### 结果摘要

CCC 调用方切换完成：Claude Code → 6100、OpenCode → 6102、Engine env → 6100，Engine 重启生效。M1 4100/4102 零影响。

### 执行明细

| 调用方 | 切换前 | 切换后 | 状态 |
|--------|--------|--------|------|
| Claude Code | 127.0.0.1:6100（已就位） | 127.0.0.1:6100 | ✅ |
| OpenCode | 127.0.0.1:6102/v1（已就位） | 127.0.0.1:6102/v1 | ✅ |
| Engine env | 192.168.3.140:4100（M1） | 127.0.0.1:6100 | ✅ 本次修改 |

- Engine 重启：kickstart 成功，新 PID 28004（ccc-engine.py）
- 备份：`settings.json.bak-ccc-6100` / `opencode.json.bak-ccc-6102` / `engine.env.bak-ccc-6100` 三份都在
- 冒烟：6100 Anthropic 出 flash 响应；6102 OpenAI 出 glm-4-flash "OK"
- **M1 零影响**：4100/4102 监听 PID 63542 未变；**M1 旧中转站未停用**（D9 停用时机由老板另定）

### 回滚

任一步需回滚：恢复 `.bak-ccc-6100`/`.bak-ccc-6102` 对应文件 + 重启 Engine 即可。

### 验收自检

| 验收标准 | 状态 |
|---------|------|
| 6100/6102 冒烟通过（双协议出模型响应） | ✅ |
| M1 4100/4102 监听不变（PID 对比） | ✅ PID 63542 未变 |
| 所有配置有备份、可一键回滚 | ✅ 3 份 .bak |
| M1 旧中转站不停用 | ✅ 未动 |
