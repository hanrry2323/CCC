# Skill: write-code

> 职能：写代码
> 库路径：skills/write-code

## 职责

按意图卡目标实现代码变更：
- 新增功能
- 修复 bug
- 重构优化

## 工作方式

1. 读取意图卡 goal + acceptance + plan_md
2. 理解 scope 范围
3. 实现代码变更
4. 跑验收探针
5. auto-commit

## 验收方式

- acceptance 探针全绿
- git diff 符合 scope

## 配套 Prompt

prompts/write-code-prompt（如有）

## 默认执行器

opencode
