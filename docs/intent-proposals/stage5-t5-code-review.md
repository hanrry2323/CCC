---
project_id: qb
title: stage5 任务5 code-review：代码审查
skill_ref: skills/code-review
prompt_ref: prompts/code-review-prompt
---

# 目标

用 code-review skill 审查 `stage5_t1_util.py` 的代码质量，输出审查报告。

# 范围

- `scripts/stage5_t5_review.md`（新建审查报告）

# 步骤概要

1. 读 `scripts/stage5_t1_util.py`
2. 审查函数正确性、边界处理、命名规范
3. 输出审查报告到 `scripts/stage5_t5_review.md`，至少 3 条审查意见

## 验收

- `DRY_RUN=true python3 -c "from pathlib import Path; p=Path('scripts/stage5_t5_review.md'); assert p.is_file() and len(p.read_text()) > 100"`
