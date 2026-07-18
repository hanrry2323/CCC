# Plan: debt-python-shebang-encoding — 统一 shebang 和 coding 声明

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

scripts/ 下 Python 脚本 shebang 不一致：有的 `#!/usr/bin/env python3`，有的 `#!/usr/bin/python3`，有的无 shebang。部分文件缺 `# -*- coding: utf-8 -*-` 声明。

## 范围

- **目标**: 所有可执行 Python 脚本统一 shebang 为 `#!/usr/bin/env python3`，所有 .py 文件加 coding 声明
- **只改文件**: `scripts/*.py`, `tests/scripts/*.py`

## 改动

1. 可执行脚本（pytest 不需要）加 `#!/usr/bin/env python3`
2. 所有 .py 文件加 `# -*- coding: utf-8 -*-`（第二行）
3. 已正确的不改
4. 不涉及 `.sh` 脚本

## 验收

- [shebang] `grep -rll 'python3' scripts/*.py | xargs head -1 | grep -c '/usr/bin/env python3'` = 所有可执行脚本数
- [coding] `grep -rL 'coding.*utf' scripts/*.py` 返回 0
- [无功能变化] `python3 -m compileall scripts/` → 0 errors
