# Plan: product-phase-limit — 限制 product_role phase 拆分不超过 2 个

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

<!-- v0.23 强制 -->

- **入口/核心文件**：`scripts/ccc-board.py`（~4100 行）、`scripts/_config.py`（~260 行）
- **当前结构要点**：
  1. `_call_claude_for_plan()`（L1028-1178）：内部 `_build_prompt()` 构造 prompt 发给 Claude，让 LLM 自行决定 phase 数——**无任何上限约束**。复杂 task 被拆 3+ phases 是直接原因
  2. `_parse_output()`（L1141-1158）：解析 Claude 返回，只验证 JSON 合法性，**不检查 phase 数量**
  3. `_generate_fallback_plan/phases()`（L1181-1208）：fallback 模式固定 1 phase，不受影响
  4. `Config` 类（`_config.py:100-202`）：没有 `max_phases` 字段，无法通过环境变量或配置调节
  5. `template/plan.plan.md`（L26）：在 "## 范围" 中只写 `Phase 数：[正整数]`，未标注上限
- **待改动点**：
  - `_config.py`：Config 类新增 `max_phases` 字段和环境变量覆盖
  - `ccc-board.py`：`_build_prompt()` 增加 phase 上限指令，`_parse_output()` 之后增加校验

---

## 范围

- **目标**：product_role 拆解 task 时硬限制 phase ≤ 2，超出的复杂 task 应拆成多个子 task
- **只改文件**：`["scripts/_config.py", "scripts/ccc-board.py"]`
- **不改文件**：`["scripts/_board_store.py", "templates/plan.plan.md", "tests/"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：Config 新增 max_phases + Prompt 增加上限指令 + 返回校验

### 做什么

当前 product_role 拆解 task 时没有 phase 数上限，LLM 常拆出 3+ phases，opencode 执行进程超时消失。
增加三重防线：

1. **配置层**：`Config.max_phases` 默认 2，支持 `CCC_MAX_PHASES` 环境变量覆盖
2. **Prompt 层**：在发给 LLM 的指令中明确标注 phase 数 ≤ 2
3. **校验层**：LLM 返回后强制检查 phase 数，超出则抛异常触发 retry

### 怎么做

**1a. `scripts/_config.py`** Config 类中新增字段（约 L133-size_hint_threshold 附近）：

```python
# ── product_role ——
max_phases: int = 2  # product_role 拆解 task 的最大 phase 数，超出抛异常
```

并在 `__post_init__()` 中（约 L186-201 的 `_env_override_*` 块）追加：

```python
_env_override_int(self, "max_phases", "CCC_MAX_PHASES")
```

**1b. `scripts/ccc-board.py`** `_build_prompt()` 中追加 phase 上限指令（L1047-1066，在 `## Phases 格式` 段落后、`## 参考历史 plan` 之前）：

```python
f"## Phase 数上限\n"
f" 重要约束：每个 task 的 phase 数**最多 2 个**。\n"
f"如果 task 复杂，应将其拆成多个子 task（每个在 backlog 中独立），\n"
f"每个子 task 不超过 2 phases。\n\n"
```

**1c. `scripts/ccc-board.py`** `_call_claude_for_plan()` 中解析后增加校验（约 L1164，在 `_parse_output(output)` 后）：

```python
max_phases = _get_cfg().max_phases
if len(phases) > max_phases:
    raise RuntimeError(
        f"phase 数 {len(phases)} 超过上限 {max_phases}"
    )
```

注意：`_parse_output` 内部已有 `try/except`，此处抛 `RuntimeError` 会自动触发简化 prompt 重试（L1165-1176 的 retry 逻辑），重试仍超限则 fallback。不需要新增重试逻辑。

### 验收清单

- [ ] Config.max_phases 默认值为 2
- [ ] 环境变量 `CCC_MAX_PHASES=3` 可覆盖为 3
- [ ] prompt 中包含 "最多 2 个" 的中文约束
- [ ] phases 数超过 max_phases 时抛 RuntimeError
- [ ] 超出后触发重试（简化 prompt retry），重试仍超限则 fallback 写单 phase
- [ ] 符合条件的 ≤2 phases 正常写文件，不额外报错
- [ ] `python3 -m compileall -q scripts/_config.py scripts/ccc-board.py` 零错误
- [ ] 不影响 product_role 正常流程（backlog 列出 / --promote 正常 task）

### 验收

- [编译检查] `python3 -m compileall -q scripts/_config.py scripts/ccc-board.py` → 0 errors
- [config 默认值] `python3 -c "from _config import Config; print(Config().max_phases)"` → 2
- [env 覆盖] `CCC_MAX_PHASES=3 python3 -c "from _config import Config; print(Config().max_phases)"` → 3
- [prompt 含约束] 走读 `_build_prompt()` 生成的 prompt 字符串，确认包含 "最多 2 个"（或 grep 确认）
- [校验生效] `python3 -c "import sys; sys.path.insert(0,'scripts/'); from ccc_board import _call_claude_for_plan; print('import ok')"` → import ok（无需 mock API）
- [regression] `python3 -m pytest tests/scripts/test_config.py -q` → 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 三重防线：config + prompt + 校验 | `feat(product): 限制 phase 拆分不超过 2 个 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/_config.py scripts/ccc-board.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/test_config.py -q`）
- [ ] diff 范围仅限 `scripts/_config.py` 和 `scripts/ccc-board.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成

---