---
project_id: qb
title: stage5 任务4 ops：看板卫生检查
skill_ref: skills/ops
prompt_ref: prompts/write-code-prompt
pipeline: ops
---

# 目标

用 ops skill 做一次看板卫生检查，验证 ops pipeline 的短路径闭环。

# 范围

- `.ccc/board/`（只读检查，不改业务码）

# 步骤概要

1. 检查 `.ccc/board` 目录存在
2. 检查 `.ccc/board/index.json` 存在
3. 输出检查结果到 `scripts/stage5_t4_ops_report.py`

# 验收意图

- `DRY_RUN=true python3 -c "from pathlib import Path; assert Path('.ccc/board').is_dir()"`
- `DRY_RUN=true python3 -c "from pathlib import Path; assert Path('scripts/stage5_t4_ops_report.py').is_file()"`
