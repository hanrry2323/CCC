# 实验 B0 · 环境冒烟（测试实例验证）

- **状态**：✅ 完成
- **批次**：B0
- **环境**：测试实例（headless code 模式）
- **日期**：2026-08-16

## 结论

**DSH 测试实例成立**：headless + `DSH_TOOLS_MODE=code` + plist 借环境 = 隔离的 code 模式 one-shot runner，run_code 全链路可跑、内层工具调用落 code-dispatch 日志、生产 web 完全不受影响。

## 方法

测试实例无需独立 profile（比计划更简）：headless profile 自带 code-runtime bundle，`DSH_TOOLS_MODE=code` 进程级开关即可进 code 模式。runner：`scripts/run-headless-code.sh`（从 web plist 借 `OPENCODE_GO_API_KEY`/`NODE_OPTIONS` 等环境，不打印密钥，加 IPv6 防护）。

三次递进探针：

1. **无 env 裸跑** → `MISSING_CREDENTIAL: opencode-go`（headless 缺 API key，生产 web 的凭据在 launchctl plist 里）
2. **借 env 跑** → 成功，但 `run_code 本会话不存在`（mode 默认 native，code-runtime 虽挂载但未激活；模型幻觉用 `node --experimental-strip-types` 等价替代——**副作用样本：模型会把缺失工具误答成已实现**）
3. **借 env + DSH_TOOLS_MODE=code** → run_code 执行成功，type-strip 警告出现，程序内 `tools.bash` 调用成功

## 证据

- 探针3 会话：`~/.dsh/sessions/--Users-fan-qx-map--/session-ef28404c-a9be-4986-aa90-462ee0808937/`
- `code-dispatch-start: 1`、`code-dispatch: 1`、`INNER-TOOL-OK` ×13（type-strip 警告即 run_code 执行证明）
- 生产 web PID 48580 探针前后均 `*:3080 LISTEN`（隔离确认）
- `DSH_TOOLS_MODE` 机制出处：`dsh-web-app/cordis.patch.yml` 注释「TEMPORARY workaround: DSH_TOOLS_MODE (native|code|both) opts a whole dsh process into Code Mode」
- code preset 内置：`dsh/config/agent-presets/code/agent.cordis.yml`（`mode: code`，行 262）

## 关键事实（后续实验都依赖）

1. **进 code 模式**：`DSH_TOOLS_MODE=code` 环境变量（进程级），headless 默认 native。
2. **借凭据**：headless 无 web 的 env，须从 `~/Library/LaunchAgents/com.deepseek.dsh-web.plist` 借 `OPENCODE_GO_API_KEY` 等（runner 已封装，不打印）。
3. **IPv6 防护**：`NODE_OPTIONS=--dns-result-order=ipv4first`（opencode.ai 有 AAAA 无 IPv6 路由）。
4. **会话隔离**：headless 每次一个全新会话，落 cwd workspace 下，不碰生产 web 会话。
5. **副作用观察**：无 run_code 时模型会幻觉等价实现——实验任务描述必须明确 run_code 存在，否则模型可能绕过。
