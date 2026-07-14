# Plan: engine-failure-lessons — 任务 quarantine 时自动记 lessons

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

<!-- v0.23 强制：Plan 必须包含此段 -->
- **入口/核心文件**：`scripts/_lessons.py`（62 行）、`scripts/ccc-engine.py`（~2300 行）、`scripts/ccc-board.py`（~4200 行）
- **当前结构要点**：
  1. `_lessons.py` 已有 3 个函数：`record_failure()` 写 `.ccc/lessons/<task_id>.json`（机器 JSON）、`get_recent_lessons()` 读取、`mark_fixed()` 标已修复
  2. `ccc-engine.py` — `_quarantine_with_notify()`（L220-241）已在 quarantine 时调用 `record_failure()` 记录机器 JSON 教训，含 `ws`、`tid`、`phase`、`reason`
  3. `ccc-board.py` — `_quarantine()`（L123-125）是 `store.quarantine()` 的薄封装，当前不记录任何 lessons；模块级 `ROOT`（L83）可获取 workspace 路径
  4. `docs/lessons.md`（2072 行，37 条 Lesson）是纯手写 Markdown 文件，**没有任何函数向其写入**。末尾以 `---` 分隔和空白换行结尾
  5. 现存 gap：机器 JSON 教训（`.ccc/lessons/`）存在但不自动写入可读的 `docs/lessons.md`，product_role 无法在下次写 plan 时直接引用
- **待改动点**：
  - `scripts/_lessons.py` — 新增 `auto_append_lesson_md()` 函数
  - `scripts/ccc-engine.py` — `_quarantine_with_notify()` 追加调用
  - `scripts/ccc-board.py` — `_quarantine()` 追加调用

---

## 范围

- **目标**：quarantine 发生时自动将失败记录追加到 `docs/lessons.md`，包含 workspace、phase、失败原因
- **只改文件**：`["scripts/_lessons.py", "scripts/ccc-engine.py", "scripts/ccc-board.py"]`
- **不改文件**：`["docs/lessons.md", "scripts/_board_store.py", "scripts/_config.py", "scripts/_exceptions.py", "tests/"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：`auto_append_lesson_md()` + engine & board 双入口调用

### 做什么

新增 `_lessons.auto_append_lesson_md()` 函数，在 quarantine 时自动向 `docs/lessons.md` 追加一条结构化教训记录。同时从 engine.py 的 `_quarantine_with_notify()` 和 board.py 的 `_quarantine()` 双入口调用，覆盖所有 quarantine 路径。

### 怎么做

**1a. `scripts/_lessons.py`** — 新增 `auto_append_lesson_md()` 函数（在 `mark_fixed` 之后）：

```python
_LESSON_HEADING_RE = re.compile(r"^## Lesson (\d+)")


def _next_lesson_number(ws_path: Path) -> int:
    """扫描 docs/lessons.md 找到最新 Lesson 编号，返回下一个。

    没有匹配到任何 Lesson 时返回 1。
    """
    lessons_md = ws_path / "docs" / "lessons.md"
    if not lessons_md.exists():
        return 1
    max_n = 0
    for line in lessons_md.read_text().split("\n"):
        m = _LESSON_HEADING_RE.match(line.strip())
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return max_n + 1


def auto_append_lesson_md(
    ws_path: Path,
    task_id: str,
    phase: int | str | None,
    error: str,
) -> None:
    """自动追加一条 Lesson 记录到 docs/lessons.md。

    格式对标已有 Lesson 结构（标题 + 元信息 + 自检提示），
    内容完全由调用方提供（不分析根因或修复方案）。
    """
    lessons_md = ws_path / "docs" / "lessons.md"
    n = _next_lesson_number(ws_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    phase_str = str(phase) if phase is not None else "N/A"
    entry = (
        "\n---\n"
        f"\n## Lesson {n}：{task_id} 进入异常状态\n"
        f"\n**项目**：`{ws_path}` | **Phase**：{phase_str} | **时间**：{timestamp}\n"
        f"\n**失败原因**：{error}\n"
        f"\n**待分析**：由 product_role 后续补充根因和修复方案\n"
    )
    with open(lessons_md, "a", encoding="utf-8") as f:
        f.write(entry)
```

需在文件头部新增 import：`import re`

**1b. `scripts/ccc-engine.py`** — `_quarantine_with_notify()`（L235-241）已有 `record_failure()` 调用，在其后追加 `auto_append_lesson_md()`：

```python
    # v0.31: 记录教训
    try:
        from _lessons import record_failure

        record_failure(ws, tid, phase, reason or "unknown", "")
    except Exception:
        pass
    # v0.32: 自动追加到 docs/lessons.md
    try:
        from _lessons import auto_append_lesson_md

        auto_append_lesson_md(ws, tid, phase, reason or "unknown")
    except Exception:
        pass
```

**1c. `scripts/ccc-board.py`** — `_quarantine()`（L123-125）新增 `auto_append_lesson_md()` 调用。board 的 `_quarantine` 知道 `ROOT`（workspace 根）但不知道 phase。对于无 phase 信息的调用，传 phase=None 让 lessons 写入 "N/A"：

```python
def _quarantine(task_id: str, reason: str) -> None:
    """将任务移入异常列（委托 FileBoardStore）"""
    store.quarantine(task_id, reason)
    # v0.32: 自动追加到 docs/lessons.md
    try:
        from _lessons import auto_append_lesson_md

        auto_append_lesson_md(ROOT, task_id, phase=None, error=reason)
    except Exception:
        pass
```

（无需额外 import — `from _lessons import auto_append_lesson_md` 是函数内延迟 import）

### 验收清单

- [ ] `auto_append_lesson_md()` 函数被正确扫描 lesson 编号并追加新条目
- [ ] 空 `docs/lessons.md` 或不存在时从 Lesson 1 开始
- [ ] `auto_append_lesson_md()` 附加内容以 `\n---\n` 作为分隔符（与已有格式一致）
- [ ] engine 的 `_quarantine_with_notify()` 在现有 `record_failure()` 后追加调用
- [ ] board 的 `_quarantine()` 在 `store.quarantine()` 后追加调用
- [ ] 两者调用均有 `try/except` 保护，不因 lessons 写入失败阻塞主流程
- [ ] 已有 Lesson 编号大于 99 时也能正确递增
- [ ] `_next_lesson_number()` 正则只匹配行首 `## Lesson` 头部，不误匹配正文中的 "Lesson"

### 验收

- [编译检查] `python3 -m compileall -q scripts/_lessons.py scripts/ccc-engine.py scripts/ccc-board.py` → 0 errors
- [语法] `python3 -c "import ast; ast.parse(open('scripts/_lessons.py').read())"` → 无异常
- [函数存在] `grep -n "def auto_append_lesson_md" scripts/_lessons.py` → 匹配
- [函数调用-engine] `grep -n "auto_append_lesson_md" scripts/ccc-engine.py` → `_quarantine_with_notify()` 内有调用（且与 record_failure 相邻）
- [函数调用-board] `grep -n "auto_append_lesson_md" scripts/ccc-board.py` → `_quarantine()` 内有调用
- [try/except] `grep -n "try:" scripts/ccc-engine.py | tail -5` → auto_append_lesson_md 调用在 try 块内
- [try/except] `grep -n "try:" scripts/ccc-board.py | tail -5` → auto_append_lesson_md 调用在 try 块内
- [编号递增] `grep -n "def _next_lesson_number" scripts/_lessons.py` → 函数存在
- [正则存在] `grep -n "_LESSON_HEADING_RE" scripts/_lessons.py` → 模块级常量存在
- [测试] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过
- [模拟写入] `python3 -c "
from pathlib import Path
import tempfile, os
md = Path(tempfile.mkdtemp()) / 'docs' / 'lessons.md'
md.parent.mkdir(parents=True)
md.write_text('## Lesson 1: T1\\n\\n---\\n\\n## Lesson 5: T5\\n')
from scripts._lessons import _next_lesson_number
assert _next_lesson_number(md.parent) == 6, f'got {_next_lesson_number(md.parent)}'
print('next lesson number: OK')
"` → 输出 `next lesson number: OK`（temp 目录下运行，不影响真实文件）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | `_lessons.py` 新增 `auto_append_lesson_md()` + engine/board 双入口调用 | `feat(lessons): quarantine 时自动追加 lessons.md (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] 全部测试通过
- [ ] diff 范围仅限 `scripts/_lessons.py`、`scripts/ccc-engine.py`、`scripts/ccc-board.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
- [ ] 新条目的 `---` 分隔符与已有格式兼容，不破坏 markdown 解析
- [ ] `try/except` 确保 lessons 写入失败时不影响 task 正常 quarantine 流程

---

## 后续步骤

完成后：
- product_role 可直接 `grep "## Lesson" docs/lessons.md | tail` 查看最新自动记录
- 后续可增加 `product_role 处理 lessons.md` 阶段：自动读取未标注 `已分析` 的条目并补充根因
- `docs/lessons.md` 自动条目达到阈值（如 100 条）后可考虑实现自动归档或分段