# Plan: evolve-complexity-20260716-055533 — 降低 validate_task_jsonl 圈复杂度（42 → ~10）

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

`scripts/_board_store.py:77` — 函数 `validate_task_jsonl` 包含 12 条独立校验规则 + strict 模式，全部内联在 150 行函数体内，每个规则都有 2-3 个 if/elif 分支。圈复杂度 42（阈值 high≥20）。

- **入口/核心文件：**
  - `scripts/_board_store.py:77-226` — `validate_task_jsonl()`，全量校验函数，150 行，无子函数拆分
  - `tests/scripts/test_validate_task_jsonl.py` — 完整的测试套件，每个规则有独立测试方法

- **当前结构要点：**
  - `validate_task_jsonl` 一个函数处理 12 条规则（id/title/status/timestamps/description/assignee/tags/note/schema_version/color_group/color_depth/complexity）+ strict 模式
  - 每个规则 2-3 个分支，外加 tags 嵌套 for 循环
  - 所有规则共享 `errors: list[str]`，追加模式，互不干扰
  - 每条规则独立，可安全提取为单独函数

- **待改动点：**
  - `scripts/_board_store.py` — 将 `validate_task_jsonl` 体内部每个规则提取为 `_validate_rule_*()` 私有函数，主函数变为规则链调用
  - 测试文件无需修改（公共 API 签名不变：`(data, *, strict) → (bool, list[str])`）

---

## 范围

- **目标**：将 `validate_task_jsonl` 圈复杂度从 42 降至 ≤10，不改变任何行为或错误信息
- **只改文件：**
  - `scripts/_board_store.py`
- **不改文件：** 所有测试文件、`scripts/ccc-board-server.py`、`scripts/tests/regression_v028.py`
- **执行方式：** `manual`
- **Phase 数：** 1

---

## 改动 1：提取每个校验规则为独立私有函数

### 做什么
把 `validate_task_jsonl` 内部的 12 条校验规则各自提取为 `_validate_rule_*()` 私有函数，每个函数接收 `data: dict` 返回 `Optional[str]`（None = 通过，string = 错误消息）。

`validate_task_jsonl` 降级为一个编排函数：调用所有规则收集错误 + 最后处理 strict 模式。行为零变化（错误消息、顺序、布尔输出全部一致）。

### 怎么做
1. **`scripts/_board_store.py`** — 在 `validate_task_jsonl` 之前新增以下 12 个私有函数：

   - `_validate_rule_id(data: dict) -> str | None`（第 110-119 行逻辑）
   - `_validate_rule_title(data: dict) -> str | None`（第 121-126 行逻辑）
   - `_validate_rule_status(data: dict) -> str | None`（第 128-133 行逻辑）
   - `_validate_rule_timestamps(data: dict) -> str | None`（第 135-144 行逻辑，注意这是唯一带 for 循环的规则，提取为独立函数后复杂度 ~4，不继续拆分）
   - `_validate_rule_description(data: dict) -> str | None`（第 146-151 行逻辑）
   - `_validate_rule_assignee(data: dict) -> str | None`（第 153-156 行逻辑）
   - `_validate_rule_tags(data: dict) -> str | None`（第 158-166 行逻辑）
   - `_validate_rule_note(data: dict) -> str | None`（第 168-171 行逻辑）
   - `_validate_rule_schema_version(data: dict) -> str | None`（第 173-176 行逻辑）
   - `_validate_rule_color_group(data: dict) -> str | None`（第 178-184 行逻辑）
   - `_validate_rule_color_depth(data: dict) -> str | None`（第 186-192 行逻辑）
   - `_validate_rule_complexity(data: dict) -> str | None`（第 194-203 行逻辑）
   - `_validate_strict_mode(data: dict) -> str | None`（第 206-224 行逻辑，strict 模式）

   每个函数的签名示例：
   ```python
   def _validate_rule_id(data: dict) -> str | None:
       """规则 1: id 必填 + sanitize 后非 invalid + 无特殊字符"""
       raw_id = data.get("id")
       if raw_id is None or not str(raw_id).strip():
           return "id: required and non-empty"
       sanitized = sanitize_id(str(raw_id))
       if sanitized == "invalid":
           return "id: contains no valid chars (only [a-zA-Z0-9_-] allowed)"
       if sanitized != str(raw_id):
           return f"id: would be sanitized from '{raw_id}' to '{sanitized}'"
       return None
   ```

2. **重构 `validate_task_jsonl`**：

   ```python
   def validate_task_jsonl(data: dict, *, strict: bool = False) -> tuple[bool, list[str]]:
       errors: list[str] = []
       if not isinstance(data, dict):
           return False, ["data must be dict"]

       # 12 条校验规则链（顺序不变，错误消息不变）
       for _validate in [
           _validate_rule_id,
           _validate_rule_title,
           _validate_rule_status,
           _validate_rule_timestamps,
           _validate_rule_description,
           _validate_rule_assignee,
           _validate_rule_tags,
           _validate_rule_note,
           _validate_rule_schema_version,
           _validate_rule_color_group,
           _validate_rule_color_depth,
           _validate_rule_complexity,
       ]:
           err = _validate(data)
           if err is not None:
               errors.append(err)

       if strict:
           err = _validate_strict_mode(data)
           if err is not None:
               errors.append(err)

       return (len(errors) == 0), errors
   ```

3. **移除**原来函数体内的 110-224 行所有内联规则代码，替换为上述编排代码。

4. **文档字串**：docstring 保留，注明"每条规则已提取为 `_validate_rule_*` 私有函数"。

### 验收清单

- [ ] 所有原有 test_validate_task_jsonl 测试通过（规则 1-11 + strict + 容错）
- [ ] 行为等价：每个规则产生的错误消息内容完全一致
- [ ] validate_task_jsonl 本身的圈复杂度 ≤ 10（通过 radon 验证）
- [ ] 每个 _validate_rule_* 函数圈复杂度 ≤ 5
- [ ] 12 个规则函数 + strict 模式函数全部声明在 module 级别（不是嵌套函数）
- [ ] 测试文件零改动
- [ ] 编译检查零错误（`python3 -m compileall -q scripts/_board_store.py`）

### 验收
- [测试通过]（参考：`python3 -m pytest tests/scripts/test_validate_task_jsonl.py -v --tb=short`）
- [复杂度验证]（参考：
  ```bash
  # 先 pip install radon，然后：
  python3 -m radon cc scripts/_board_store.py -s -n C
  # 应看到 validate_task_jsonl 复杂度 ≤ 10，各 _validate_rule_* ≤ 5
  ```
  radon 未安装时以 `python3 -c "import ast; import sys; ..."` 手动计算圈复杂度作为 fallback）
- [行为等价]（参考：
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'scripts')
  from _board_store import validate_task_jsonl
  # 验证 id 校验
  ok, errs = validate_task_jsonl({'id': 'bad id'})
  assert 'id: contains' in str(errs), f'got {errs}'
  # 验证完整 task 通过
  ok, errs = validate_task_jsonl({'id': 'ok', 'title': 't', 'status': 'backlog', 'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z'})
  assert ok, f'got {errs}'
  print('Behavior match: OK')
  "
  ```

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 提取 validate_task_jsonl 的 12 条规则 + strict 模式为独立私有函数 | `refactor(board): extract validate_task_jsonl rules into _validate_rule_* functions (cc 42→~10)` |

---

## 全局验收清单

- [ ] 编译/类型检查零错误（`python3 -m compileall -q scripts/_board_store.py`）
- [ ] 测试全部通过：`python3 -m pytest tests/scripts/test_validate_task_jsonl.py tests/scripts/test_board_store.py -v --tb=short -q`
- [ ] diff 范围仅限 `scripts/_board_store.py`
- [ ] 1 个 phase 对应 1 个 commit
- [ ] phases.json 与 plan phase 数一致（1）
- [ ] Plan 中所有验收意图全部达成