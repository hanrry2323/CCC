# Plan: e2e-chat-greet — greet helper

> 撰写：chat-seed | 执行：ccc-dev（auto）

---

## 当前代码状态

- CCC 脚本目录 `scripts/` 尚无 `_e2e_greet.py`
- 测试目录 `tests/scripts/` 可新增单测

---

## 范围

- **目标**：新增纯函数 `greet(name)` 并配 pytest 验收
- **只改文件**：`scripts/_e2e_greet.py`, `tests/scripts/test_e2e_greet.py`
- **不改文件**：其它任何文件
- **执行方式**：`auto`
- **Phase 数**：1

---

## 改动 1：greet 工具函数

### 做什么
提供 `greet(name: str) -> str`：返回 `hello, {name}`（strip）；空/空白 name 返回 `hello`。

### 怎么做
- 新建 `scripts/_e2e_greet.py` 实现 `greet`
- 新建 `tests/scripts/test_e2e_greet.py` 覆盖正常与空串

### 验收清单

- [ ] `greet("Ada") == "hello, Ada"`
- [ ] `greet("") == "hello"` 且 `greet("  ") == "hello"`
- [ ] `pytest tests/scripts/test_e2e_greet.py -q` 全绿

### 验收
参考：`python3 -m pytest tests/scripts/test_e2e_greet.py -q`
