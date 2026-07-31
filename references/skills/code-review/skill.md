# Skill: code-review

> 职能：代码审查
> 库路径：skills/code-review

## 职责

审查代码变更，检查：
- 逻辑正确性
- 安全漏洞
- 性能问题
- 代码风格一致性

## 工作方式

1. 读取 git diff 或指定文件
2. 逐文件审查
3. 输出审查报告（问题列表 + 严重级别 + 修复建议）

## 验收方式

- 审查报告输出为 Markdown
- 无 P0/P1 问题 = 通过

## 配套 Prompt

prompts/code-review-prompt

## 默认执行器

opencode（可被意图卡 executor 字段覆盖）
