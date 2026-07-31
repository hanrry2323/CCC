# Skill: script-seed

> 职能：脚本种子 / 机械探针
> 库路径：skills/script-seed

## 职责

处理机械意图探针 / 卫生卡 / 脚本种子类任务：
- paper_intent_probe
- 意图探针
- 纸面探针
- script-seed
- 卫生卡（git add / committer / 单 commit）

## 工作方式

1. 识别探针类型（机械探针 vs 业务探针）
2. 执行探针命令（python3 / pytest / DRY_RUN）
3. 落盘探针结果
4. auto-commit（机械探针专用）

## 验收方式

- 探针命令可重放
- 结果落盘

## 配套 Prompt

prompts/write-code-prompt（复用写码 prompt）

## 默认执行器

python
