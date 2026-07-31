# Skill: ops

> 职能：运维 / 脚本执行
> 库路径：skills/ops

## 职责

处理运维类任务：
- shell 脚本执行
- 配置变更
- 日志轮转
- 监控探活
- 卫生 epic（commit-folder-hygiene）

## 工作方式

1. 读取运维意图（pipeline=ops / cli / shell）
2. 执行 shell 命令 / 脚本
3. 验证执行结果
4. auto-commit（如涉及配置变更）

## 验收方式

- 命令退出码 0
- 结果符合预期（日志 / 文件 / 状态）

## 配套 Prompt

prompts/write-code-prompt（复用写码 prompt）

## 默认执行器

cli
