---
project_id: qb
title: stage5 闭环烟测：utils 工具函数
skill_ref: skills/write-code
prompt_ref: prompts/write-code-prompt
---

# 目标

给 qb 项目落地一个简单工具函数 `format_pct`，验证 stage5 拆卡闭环：方案 → splitter 拆卡 → Engine 消费 → released。

# 范围

- `scripts/stage5_smoke_util.py`（新建，含 `format_pct` 函数）

# 步骤概要

1. 新建 `scripts/stage5_smoke_util.py`
2. 实现 `def format_pct(value: float, digits: int = 1) -> str`：将 0.1234 格式化为 "12.3%"
3. 写一行 assert 验证

# 验收意图

- `DRY_RUN=true python3 -c "from pathlib import Path; assert Path('scripts/stage5_smoke_util.py').is_file()"`
- `DRY_RUN=true python3 -c "import sys; sys.path.insert(0,'scripts'); from stage5_smoke_util import format_pct; assert format_pct(0.1234) == '12.3%'; print('ok')"`
