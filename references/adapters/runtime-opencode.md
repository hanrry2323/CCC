# Runtime: OpenCode

OpenCode 环境下的 CCC 协议加载方式。通过 `system_prompt_file` 参数直接注入 SKILL.md。

---

## 何时使用

- 工作环境是 OpenCode（由 `opencode serve` 提供后端）
- 需要 OpenCode 的持久会话 + 历史记忆能力
- 需要在终端快速执行 CCC 任务

## 安装

复制 SKILL.md 到 OpenCode 能读到的路径，配置 OpenCode 加载：

```bash
# 方法 1: 全局 system_prompt_file
echo 'system_prompt_file = "/Users/apple/program/CCC/SKILL.md"' >> ~/.opencode/config.toml

# 方法 2: 每 project 级
echo 'system_prompt_file = "/Users/apple/program/CCC/SKILL.md"' >> <project>/.opencode/config.toml

# 方法 3: 手动加载（每次启动指定）
opencode --system-prompt-file /Users/apple/program/CCC/SKILL.md
```

## 使用

配置好后启动 OpenCode：

```bash
opencode serve
```

OpenCode 会话自动带有 CCC 上下文。键入"跑 CCC 任务"即可开始。

### Executor 在 OpenCode 中执行

```bash
opencode exec "按 /Users/apple/program/CCC/SKILL.md 的 Procedure 跑此 plan"
```

### Verifier 在 OpenCode 中执行

```bash
opencode exec "作为 ccc-verifier，独立验收此任务，≥3 adversarial probes"
```

## 注意事项

| 注意点 | 说明 |
|--------|------|
| system_prompt_file 路径 | 必须绝对路径，OpenCode 环境变量不确定 |
| 与 OpenCode memory 交互 | SKILL.md 定义流程，OpenCode 的 memory-store 记忆历史 |
| model 选择 | OpenCode 默认用 claude-3-5-sonnet，建议改为 flash（等效 Claude model） |
