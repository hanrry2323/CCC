# CCC Auto-Growth v1 — Cursor 执行提示词

> 目标：把 6 个架构成语全部实现，CCC 从 30% 自动率到 90%
> 工作区：`/Users/apple/program/CCC`
> 只改 4 个文件 + 增 1 个新文件
> 不改：Engine 主循环、Board JSONL 格式、中转站、SKILL.md、.ccc/ 契约

---

## 全局规则（所有 phase 通用）

1. **只动我列的行**，不重构不改 style
2. **try/except 包裹所有新逻辑**，失败不崩 Engine
3. **Python 3.14+**，type hints 可选
4. **每个 phase 完成后 `python3 -m compileall scripts/`** 确认语法正确
5. **先读文件再改**，文件可能已被前一个 phase 修改

---

## Phase 1：VERSION/CHANGELOG 自动化

**改** `scripts/ccc-board.py`

### 在文件末尾追加两个函数（kb_role 可以调用它们）

```python
def _bump_version(ws_path: Path) -> str:
    """读取 VERSION 文件，bump patch version，写回。返回新版本号。"""
```

```python
def _append_changelog(ws_path: Path, tid: str, new_version: str) -> None:
    """在 CHANGELOG.md 末尾追加一条版本条目。"""
```

这两个函数的 `ws_path` 从 `_get_workspace()` 或手动传。kb_role 函数的当前签名是 `def kb_role() -> dict`，但内部有 `ws_path: Path`。你需要在 `kb_role` 函数内部（`ccc-board.py:2334` 行附近），找到调用位置，在移入 released 后追加调用：

```python
# 在 move_task(task_id, "verified", "released") 之后（约行 2411）
try:
    new_ver = _bump_version(ws_path)
    _append_changelog(ws_path, task_id, new_ver)
except Exception as exc:
    _log.warning("version bump failed (non-blocking): %s", exc)
```

逻辑：
- `_bump_version`: 读 `ws_path / "VERSION"` 文件，假设格式 `v0.29.0` → `v0.29.1`
- `_append_changelog`: 读 `ws_path / "CHANGELOG.md"`，在 `## [v0.x]` 最旧版本条目之上插入新条目，格式参照已有条目
- 用 `git add` + `git commit` 自动提交（仅在 VERSION/CHANGELOG 有改动时）
- 失败不阻塞（try/except）

### 验证

```bash
# 手动测试
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from ccc_board import _bump_version
from pathlib import Path
# 只测试不写
print('import OK')
"
```

---

## Phase 2：Model tier 代码化

**改** `scripts/_config.py`

### 在文件末尾追加 ModelTier 数据类和 model 配置

```python
@dataclass
class ModelTier:
    """模型梯队配置"""
    name: str
    description: str
    default_provider: str      # 中转站模型名
    fallback_providers: list[str]  # 降级链, 优先级从高到低
    timeout_scale: float = 1.0  # 相对基准超时倍率
    max_retries: int = 3
```

### 在 Config dataclass 内新增字段

在 `Config` 类（约行 100-120）追加：

```python
model_tiers: dict[str, ModelTier] = field(default_factory=lambda: {
    "pro": ModelTier(
        name="pro",
        description="高端模型 - 架构设计 / 重构 / 审查",
        default_provider="sonnet",
        fallback_providers=[],
        timeout_scale=2.0,
        max_retries=5,
    ),
    "flash": ModelTier(
        name="flash",
        description="主力模型 - 日常开发 / 拆任务 / 对话",
        default_provider="deepseek-v4-flash",
        fallback_providers=["deepseek-v4-flash"],
        timeout_scale=1.0,
        max_retries=3,
    ),
    "code": ModelTier(
        name="code",
        description="免费模型 - 自动化开发 bulk 工作",
        default_provider="MiniMax-M3",
        fallback_providers=["xfyun-code", "zhipu-glm47-flash"],
        timeout_scale=1.5,
        max_retries=3,
    ),
})
```

### 校验

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from _config import Config
c = Config()
print('model_tiers:', list(c.model_tiers.keys()))
assert 'flash' in c.model_tiers
"
```

---

## Phase 3：product role 加固

**改** `scripts/ccc-board.py`

### 修改 `_call_claude_for_plan()` 函数（约行 942）

增加分段写入 + phases 解析重试：

1. **大 prompt 处理**：如果 `len(prompt) > 60000`，改为写临时文件 + `claude -p "Read attached file..." --file tmp_path` 方式（参考 `scripts/opencode-exec.py:120-141` 的实现模式）

2. **phases 解析失败重试**：在 claude CLI 输出后，解析 phases 部分。如果 JSON parse 失败，用简化 prompt 重试 1 次（截掉 `ref_plans` 部分减少上下文）

3. **失败回退**：如果第二次也失败，写入 `.ccc/product_fallback/{task_id}.plan.md` + 创建 `.ccc/product_fallback/{task_id}.failed` 标记文件。不要抛异常（让 caller 能处理）

### 验证

```bash
python3 -m compileall scripts/
```

---

## Phase 4：Engine 自适应调参

**改** `scripts/ccc-engine.py`

### 在 engine_loop 函数内（约行 640-695 之间），已有 `aggregate_stats(ws)` 调用的位置

添加自适应调参逻辑。在 `if iteration % 6 == 0:` 块内，`aggregate_stats(ws)` 调用之后加：

```python
# v0.31: 自适应调参（读 summary.json → 调整 timeout/retry）
try:
    summary = load_summary(ws)
    if summary and summary.get("total_events", 0) > 5:
        task_stats = summary.get("task_stats", {})
        total = task_stats.get("total", 0)
        failed = task_stats.get("failed", 0)
        if total > 0:
            fail_rate = failed / total
            # 失败率 > 40% → 增加 retry
            if fail_rate > 0.4 and MAX_RETRY < 5:
                engine_log(f"[auto-tune] fail_rate={fail_rate:.0%}, MAX_RETRY={MAX_RETRY} (adjusting)")
                # MAX_RETRY 是模块级变量，用 global 修改
                global MAX_RETRY
                MAX_RETRY = min(MAX_RETRY + 1, 5)
            # 失败率 < 10% 且 retry > 2 → 减少 retry
            elif fail_rate < 0.1 and MAX_RETRY > 2:
                engine_log(f"[auto-tune] fail_rate={fail_rate:.0%}, MAX_RETRY={MAX_RETRY} (reducing)")
                MAX_RETRY = max(MAX_RETRY - 1, 2)
except Exception as exc:
    engine_log(f"[auto-tune] error: {exc}")
```

**注意**：
- `MAX_RETRY` 是模块级全局变量（约行 59-62），用 `global MAX_RETRY` 声明
- 不影响其他使用 MAX_RETRY 的地方
- 只读 `load_summary`（已在顶部 import 了）

### 验证

```bash
python3 -m compileall scripts/
```

---

## Phase 5：Lessons Pipeline

**新增** `scripts/_lessons.py`

### 文件内容（约 150 行）

三个函数：

```python
def record_failure(ws_path: Path, task_id: str, phase: str, error: str, analysis: str = "") -> dict:
    """记录一次任务失败到 .ccc/lessons/{task_id}.json
    
    写入格式：
    {
        "task_id": "...",
        "phase": 1,
        "error": "...",
        "analysis": "...",
        "timestamp": "2026-07-13T22:00:00",
        "fixed": false
    }
    """
```

```python
def get_recent_lessons(ws_path: Path, count: int = 30) -> list[dict]:
    """读取 .ccc/lessons/ 下所有 json，按 timestamp 排序，返回最近 count 条。"""
```

```python
def mark_fixed(ws_path: Path, task_id: str) -> bool:
    """标记某条教训已修复（fixed: true）。"""
```

### 改 `scripts/ccc-engine.py`

在 `_quarantine_with_notify()` 或调用位置附近（约行 124-135），添加 lessons 记录调用：

找到 `_quarantine_with_notify` 函数的调用位置（约行 297-299），在 quarantine 后追加：

```python
# v0.31: 记录教训
try:
    from _lessons import record_failure
    record_failure(ws, tid, cur_phase or 1, error_msg or "unknown", "")
except Exception:
    pass
```

`cur_phase` 和 `error_msg` 需要从上下文提取。确认这些变量在调用位置是否可获取。如果不可获取，从 result 字典读取。

### 改 `scripts/ccc-board.py` 中 `product_role()`

在 `_call_claude_for_plan()` 调用之前（约行 942），注入 lessons context：

```python
# v0.31: 注入 lessons 上下文
try:
    from _lessons import get_recent_lessons
    recent = get_recent_lessons(ws_path if 'ws_path' in dir() else ROOT)
    if recent:
        lessons_text = "\n".join(
            f"- [{l.get('task_id','?')}] phase={l.get('phase')}: {l.get('error','')[:100]}"
            for l in recent[:10]
            if not l.get('fixed')
        )
        if lessons_text:
            prompt += f"\n\n## 近期教训（参考，避免重复）\n{lessons_text}"
except ImportError:
    pass
```

### 验证

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from _lessons import record_failure, get_recent_lessons
from pathlib import Path
ws = Path('.')
r = record_failure(ws, 'test-task', 1, 'test error')
print('record:', r)
ls = get_recent_lessons(ws)
print('lessons count:', len(ls))
" 2>&1
rm -f .ccc/lessons/test-task.json
```

---

## Phase 6：quarantine 分析 + 自修

**改** `scripts/ccc-engine.py`

### 在 `_retry_abnormal_dev_failures()` 函数内（约行 360-390）

追加重试前分析 + 反馈：

当前 `_retry_abnormal_dev_failures()` 只是移回 planned。增加：

```python
def _retry_abnormal_dev_failures(ws: Path) -> None:
    """原有逻辑：扫 abnormal → 冷却到期 → 移回 planned
    
    追加：读 lessons → 如果有 auto_fix 标记 → 应用后再移回
    """
    # ... 原有逻辑保留不动 ...
    
    # v0.31: 每次移回前检查 lessons 是否有建议
    try:
        from _lessons import get_recent_lessons
        recent = get_recent_lessons(ws)
        for task_id in moved_back:  # 需要知道哪些 task 被移回
            for lesson in recent:
                if lesson.get("task_id") == task_id and not lesson.get("fixed"):
                    _log.info("[lessons-reapply] %s: %s", task_id, lesson.get("error", "")[:80])
    except Exception:
        pass
```

**注意**：当前 `_retry_abnormal_dev_failures()` 可能没有收集移回的 task_id 列表。你需要：
1. 在函数内加一个 `moved_tasks = []` 收集被移动的 task_id
2. 循环结束后用 `moved_tasks` 查 lessons

**保留原有逻辑不变**，只追加。

### 验证

```bash
python3 -m compileall scripts/
```

---

## 全部验证

每个 phase 手动跑完后，最后跑一次完整验证：

```bash
# 1. 语法检查
python3 -m compileall scripts/

# 2. import 测试
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from _config import Config
from _lessons import record_failure, get_recent_lessons
from ccc_board import _bump_version, _append_changelog
print('All imports OK')
c = Config()
assert 'flash' in c.model_tiers
print('Model tiers:', list(c.model_tiers.keys()))
"

# 3. 清理测试文件
rm -f .ccc/lessons/test-task.json scripts/__pycache__/*

# 4. git diff 确认只改了目标文件
git diff --name-only
# 预期:
#   scripts/_config.py
#   scripts/ccc-board.py
#   scripts/ccc-engine.py
#   scripts/_lessons.py
```

---

## 不改的清单（确认）

| 文件 | 原因 |
|------|------|
| `scripts/ccc-engine.py` 的 `engine_loop()` 主循环结构 | 只追加，不改迭代逻辑 |
| `scripts/ccc-board.py` 的 7 角色调用框架 | 不改角色接口 |
| `scripts/_board_store.py` | Board 存储层不动 |
| `scripts/_executor.py` | 执行器不动 |
| `.ccc/` 下任何文件 | 契约层不动 |
| `docs/` 下任何文件 | 文档不动 |
| `templates/` | 模板不动 |
| `tests/` | 测试不动 |
