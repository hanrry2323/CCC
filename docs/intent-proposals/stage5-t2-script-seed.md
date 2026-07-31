---
project_id: qb
title: stage5 任务2 script-seed：纸面探针
skill_ref: skills/script-seed
prompt_ref: prompts/write-code-prompt
---

# 目标

用 script-seed skill 机械落地一个纸面探针脚本，验证 script-seed 短路径闭环。

# 范围

- `scripts/stage5_t2_probe.py`（新建）

# 步骤概要

1. 新建 `scripts/stage5_t2_probe.py`
2. 实现 `def paper_check() -> str`：返回 "paper-ok"
3. DRY_RUN 模式下直接可执行

# 验收意图

- `DRY_RUN=true python3 scripts/stage5_t2_probe.py`
