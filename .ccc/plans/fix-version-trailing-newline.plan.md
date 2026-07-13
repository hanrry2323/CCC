# Plan: fix-version-trailing-newline — VERSION 文件格式规范化（换行符处理）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-board.py`（`_bump_version` 函数，行 3794-3809）
- **当前结构要点**：
  - `VERSION` 文件内容为 `v0.29.0\n`（8 字节：7 字符 + 0x0a）
  - `_bump_version()`（行 3794）读取时用 `.strip()` 去换行（行 3801），但两处写回都追加 `+ "\n"`（行 3799、3808）
  - 另一处读 VERSION 在 `kb_role`（行 2420），同样用 `.strip()`——安全
  - 无其他写 VERSION 的地方，不改动的风险全部集中在这两处 `write_text`
- **待改动点**：`scripts/ccc-board.py:3799,3808` —— 两处 `write_text(new_version + "\n")` 去掉 `+ "\n"`

---

## 范围

- **目标**：`_bump_version()` 写 VERSION 不再追加换行，使文件严格等于版本号字符串
- **只改文件**：`scripts/ccc-board.py`
- **不改文件**：`.ccc/` 下任何文件、其他脚本、测试文件、`VERSION`（文件内容不变，只改写出逻辑）
- **执行方式**：`manual`
- **Phase 数**：1

---

## Phase 1：去掉 _bump_version 两处写 VERSION 的 `+ "\n"`

### 做什么

`_bump_version()` 行 3799（新建文件）和行 3808（bump 写回）都写了 `new_version + "\n"`，导致 VERSION 文件总是以换行结尾。外部工具（如 shell `cat VERSION` 拼接字符串、其他代码直接 `read_text()` 不 strip）会读到带换行的版本号。

规范化：写时去掉 `+ "\n"`，VERSION 内容严格等于版本号字符串（如 `v0.29.0`）。

读取端全部使用 `.strip()` 或类似方法，不受影响。

### 怎么做

两行改动，均在 `scripts/ccc-board.py`：

1. **行 3799**：`version_file.write_text(new_version + "\n")` → `version_file.write_text(new_version)`
2. **行 3808**：`version_file.write_text(new_version + "\n")` → `version_file.write_text(new_version)`

### 验收清单

- [ ] 新建 VERSION 文件时不写入尾随换行
- [ ] bump 写回时不写入尾随换行
- [ ] 所有 VERSION 读取方（`.strip()`）不受影响
- [ ] 无因去掉换行引发的意外行为

### 验收

- `python3 -m py_compile scripts/ccc-board.py` 语法通过
- `grep -n 'write_text.*VERSION' scripts/ccc-board.py` 确认两条 write 均不带 `+ "\n"`
- `python3 -c "exec(open('scripts/ccc-board.py').read()); from pathlib import Path; import tempfile; t=Path(tempfile.mktemp()); t.write_text('v0.29.0\n'); v=_bump_version(t.parent); assert t.read_text()==v, f'VERSION content mismatch: got {t.read_text()!r} vs {v!r}'"` 通过（bump 后文件内容等于返回值，不带换行）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 去掉 `_bump_version` 写 VERSION 的 `+ "\n"` | `fix(board): VERSION 文件写时不再追加尾随换行 (phase 1/1)` |

---

## 全局验收清单

- [ ] `python3 -m py_compile scripts/ccc-board.py` 通过
- [ ] diff 仅限 `scripts/ccc-board.py`，且仅 2 行改动
- [ ] 1 个 phase 对应 1 个 commit
- [ ] phases.json 与 plan phase 数一致
- [ ] 所有验收意图全部达成

---

## 后续步骤

落地后 VERSION 文件（当前 `v0.29.0\n`）内容不变，后续 bump 写回时不带换行。建议 dev 角色执行后确认 VERSION 文件内容为 `v0.29.0`（无尾随换行）。