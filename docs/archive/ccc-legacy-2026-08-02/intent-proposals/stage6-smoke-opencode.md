---
title: stage6 烟测：opencode 执行 + warmup 验证
skill_ref: skills/write-code
prompt_ref: prompts/write-code-prompt
---

## 目标
在 qb 仓内创建一个简单的测试文件 `warmup_test.py`，验证 warmup probe 生效。

## 范围
- `warmup_test.py`

## 步骤概要
- 创建 `warmup_test.py`，包含一个简单函数和测试
- 运行 `python3 warmup_test.py` 验证

## 验收
- DRY_RUN=true python3 -c "
import sys; sys.path.insert(0, '.')
from warmup_test import greet
assert greet('CCC') == 'Hello, CCC!'
print('opencode warmup 验证通过')
"