---
project_id: qb
title: stage5 任务3 bug-fix：修复返回错误
skill_ref: skills/bug-fix
prompt_ref: prompts/bug-fix-prompt
---

# 目标

用 bug-fix skill 修复一个已知返回错误：`stage5_t1_util.py` 的 `parse_pct` 对负数输入处理有误。

# 范围

- `scripts/stage5_t3_fix.py`（新建，修复版）

# 步骤概要

1. 新建 `scripts/stage5_t3_fix.py`
2. 实现 `def parse_pct_fixed(s: str) -> float`：负数格式 "-12.3%" 解析为 -0.123
3. 写 assert 验证负数路径

# 验收意图

- `DRY_RUN=true python3 -c "from pathlib import Path; assert Path('scripts/stage5_t3_fix.py').is_file()"`
- `DRY_RUN=true python3 -c "import sys; sys.path.insert(0,'scripts'); from stage5_t3_fix import parse_pct_fixed; assert parse_pct_fixed('-12.3%') == -0.123; print('ok')"`
