---
project_id: qb
title: stage5 任务1 write-code：工具函数实现
skill_ref: skills/write-code
prompt_ref: prompts/write-code-prompt
---

# 目标

用 write-code skill 落地一个工具函数 `parse_pct`，验证 write-code 类型任务的完整闭环。

# 范围

- `scripts/stage5_t1_util.py`（新建）

# 步骤概要

1. 新建 `scripts/stage5_t1_util.py`
2. 实现 `def parse_pct(s: str) -> float`：将 "12.3%" 解析为 0.123
3. 写一行 assert 验证

## 验收

- `DRY_RUN=true python3 -c "from pathlib import Path; assert Path('scripts/stage5_t1_util.py').is_file()"`
- `DRY_RUN=true python3 -c "import sys; sys.path.insert(0,'scripts'); from stage5_t1_util import parse_pct; assert abs(parse_pct('12.3%') - 0.123) < 1e-9; print('ok')"`
