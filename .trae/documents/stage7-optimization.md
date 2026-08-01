# 阶段 7：CCC 流程优化（基于 stage6 验证结果）

> **状态**：待执行
> **基准**：stage6 5/5 released 验证通过，但观察到 4 类待优化问题
> **范围**：Splitter 主链路修复 + 并发队列消费 + warmup 验证

---

## 一、Summary

**基于 stage6 全链路验证发现的 3 类问题，进行针对性优化：**
1. **Splitter 主链路**：LLM(flash) 未产出 CHILDREN section，contract loop 5 次 exhausted，全部走 fallback
2. **Splitter 并发**：flock 单实例保护导致 t2-t5 拿不到锁直接退出，需串行手动重跑
3. **warmup 未验证**：min-pipeline 模式下所有任务跳过 opencode 执行，warmup probe 从未被触发

---

## 二、Current State Analysis（stage6 埋点观察）

### 2.1 已验证可用 ✅

| 项 | stage6 证据 |
|----|------------|
| WP3 优雅降级 | 主链路失败后正确走 fallback，不 failed |
| main_chain_error 透传 | 已修复到 result.jsonl（第二个 commit 7598b41） |
| 5/5 fallback 拆卡 + released | 全部任务验收通过，0 abnormal |
| recover.log + reopen.log | 文件已创建 |
| claude-agent-sdk + CLI + relay | 全部就绪 |

### 2.2 待优化问题 ❌

| # | 问题 | 影响 | 根因 |
|---|------|------|------|
| P1 | 主链路 5 次 exhausted | 全走 fallback，浪费 claude-sdk 能力 | LLM(flash) 输出未含 `---CHILDREN---` 标记；`parse_fanout_output` 严格匹配 |
| P2 | 并发方案 splitter 跳过 | 5 投 1 拆，4 个需手动重跑 | `flock(LOCK_EX\|LOCK_NB)` 非阻塞，其他进程直接退出 |
| P3 | warmup 未实际触发 | 无法验证 warmup 有效性 | min-pipeline 模式下用 `verify→done` 快通，从未调用 opencode |

---

## 三、Proposed Changes（3 个 Work Package）

### WP1：Splitter 主链路修复（让 CHILDREN 可被正确产出）

**目标**：让主链路能成功产出 CHILDREN section，从 fallback 升级为主链路拆卡。

#### WP1.1：修复 parse_fanout_output 兼容性

**问题**：`parse_fanout_output` 严格要求 `---CHILDREN---` / `---END_CHILDREN---` 标记。LLM 产出可能：
- 包在 markdown code fence 中
- 用了 `---CHILDREN---` 但内容 JSON 格式有偏差
- 用了 `---CHILDREN---` 但前后有多余空格/换行

**文件**：`scripts/_product_fanout.py`
**位置**：`parse_fanout_output` 函数（L326-385）

**改动**：在 CHILDREN 正则匹配失败时，增加宽松回退：
1. 先去 fence 化（strip ```json / ``` 包裹）
2. 尝试直接找 JSON 数组（`[` 开头 `]` 结尾的最外层块）
3. 再尝试找 `---CHILDREN---` 残片

```python
# 宽松回退：先尝试从 markdown fence 中提取
if not cm:
    # 1. 去 fence
    stripped = re.sub(r'```(?:json)?\s*', '', output, flags=re.I)
    # 2. 找 ---CHILDREN--- 残片
    cm = re.search(
        r"---CHILDREN---\s*\n?(.*?)\n?---END_CHILDREN---", stripped, re.DOTALL
    )
if not cm:
    # 3. 直接找最外层 JSON 数组
    bracket_match = re.search(r'(\[\s*\{.*?\}\s*\])', output, re.DOTALL)
    if bracket_match:
        try:
            children = _loads_children_json(bracket_match.group(1))
            return brief, children
        except (ValueError, json.JSONDecodeError):
            pass
```

#### WP1.2：增加微循环次数

**问题**：当前 `CCC_PRODUCT_MICRO_LOOPS=5`（默认），5 次 exhausted 后走 fallback。考虑到 LLM 冷启动、格式适应等，适当增加次数。

**文件**：`scripts/_product_session.py`
**位置**：L20

**改动**：
```python
MAX_MICRO_LOOPS = int(os.environ.get("CCC_PRODUCT_MICRO_LOOPS", "8") or "8")
```

从 5 增加到 8。同时环境变量可覆盖，方便调试时设更大值。

#### WP1.3：error message 回传加入 lint 信息

**问题**：当前 contract loop 的 `last_error` 仅包含 "CHILDREN section not found"，没有 LLM 实际输出的片段，难以诊断。

**文件**：`scripts/_product_session.py`
**位置**：`run_contract_loop` 的 except 分支（L225-238）

**改动**：在 error message 中追加 LLM 实际输出的前 200 字符：
```python
except Exception as exc:
    last_error = str(exc)
    # R-TRACE: 追加 LLM 实际输出片段，辅助诊断
    _log.warning(
        "[product-session] %s loop %d/%d %s\noutput(%.0f): %s",
        task_id, i + 1, loops, last_error[:200],
        len(turn_text), turn_text[:300],
    )
    # 原本的 user_msg 逻辑不变
```

#### WP1.4：提醒类 prompt 增强

**问题**：LLM 在 `build_fanout_prompt` 末尾的 repair_hint 中已经收到格式约束，但可能被长 prompt 淹没。

**文件**：`scripts/_product_session.py`
**位置**：`run_contract_loop` 的 repair_hint（L129-135）

**改动**：增强 repair_hint 中的格式约束，加上 MARKDOWN CODE FENCE 的禁止强调：
```python
repair_hint = (
    ...
    if mode == "epic"
    else "\n\n硬约束：只输出 ---EPIC_BRIEF--- / ---CHILDREN--- 契约块；"
    "CHILDREN 必须是可 json.loads 的 JSON 数组。"
    "**禁止**包在 markdown code fence（```json```）内，"
    "直接输出纯文本契约块。"
)
```

---

### WP2：Splitter 并发队列消费（拿到锁后消费所有 pending 方案）

**目标**：让 splitter 拿到锁后消费所有 pending 方案，而非只处理一个。

#### WP2.1：main() 中扫描所有 pending 方案

**问题**：当前 `main()` 处理完一个 proposal 后直接返回，锁释放后下一个 splitter 才能获取锁。

**方案**：在 `main()` 中，拿到锁后扫描 workspace 的 `intent-proposals` 目录，找到所有 `status != "ok"` 且 `status != "failed"` 的方案，逐个处理。

**文件**：`scripts/ccc-intent-splitter.py`
**位置**：`main()` 函数（L468-620）

**改动**：
```python
def main(proposal_id: str, project_id: str) -> dict:
    """主流程：读方案 → 创建 epic → fanout → 附 skill_ref → wake engine → 审计。"""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        _log.warning("splitter 已在运行，跳过 proposal=%s", proposal_id)
        return {"ok": False, "error": "splitter_busy"}

    workspace = _resolve_workspace(project_id)
    if not workspace.is_dir():
        msg = f"workspace 不存在: {workspace}"
        return {"ok": False, "error": msg}

    # R-CONSUME: 拿到锁后扫描所有 pending 方案，逐个消费
    # 先处理传入的 proposal_id，再扫描其他 pending 方案
    pending_ids = _scan_pending_proposals(workspace, proposal_id)
    results = []
    for pid in pending_ids:
        _log.info("splitter 消费 pending proposal=%s", pid)
        result = _process_one(workspace, project_id, pid)
        results.append(result)
    
    # 返回聚合结果
    ...
```

新增 `_scan_pending_proposals` 函数：
```python
def _scan_pending_proposals(workspace: Path, primary_id: str) -> list[str]:
    """扫描 intent-proposals 目录，返回所有待消费的 proposal_id 列表。
    
    primary_id 排在最前，其他按 mtime 排序。
    """
    from _board_store import FileBoardStore
    prop_dir = workspace / ".ccc" / "intent-proposals"
    if not prop_dir.is_dir():
        return [primary_id]
    
    pending = []
    for f in sorted(prop_dir.glob("*.md"), key=lambda p: p.stat().st_mtime):
        pid = f.stem  # 去掉 .md 后缀
        result_file = prop_dir / f"{pid}.result.jsonl"
        if result_file.exists():
            last_status = _read_last_status(result_file)
            if last_status in ("ok", "failed"):
                continue  # 已处理完毕
        pending.append(pid)
    
    # primary_id 排最前，其余去重
    seen = {primary_id}
    ordered = [primary_id]
    for pid in pending:
        if pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    return ordered
```

新增 `_read_last_status` 辅助函数：
```python
def _read_last_status(result_file: Path) -> str:
    """读取 result.jsonl 最后一行的事件状态。"""
    try:
        for line in result_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            evt = json.loads(line)
            status = str(evt.get("status") or "")
        return status
    except (json.JSONDecodeError, OSError):
        return ""
```

将现有 `main()` 的 try 块内容抽取为 `_process_one(workspace, project_id, proposal_id) -> dict`：
```python
def _process_one(workspace: Path, project_id: str, proposal_id: str) -> dict:
    """处理单个 proposal。"""
    _t0 = time.monotonic()
    _append_audit(workspace, proposal_id, {
        "status": "running",
        "project_id": project_id,
        "workspace": str(workspace),
    })
    # 1. 读方案
    try:
        _t1 = time.monotonic()
        prop = _read_proposal(workspace, proposal_id)
        read_ms = int((time.monotonic() - _t1) * 1000)
    except Exception as exc:
        _append_audit(workspace, proposal_id, {"status": "failed", "error": str(exc)})
        return {"ok": False, "error": str(exc), "proposal_id": proposal_id}
    # ... 后续步骤不变（从现有 main() 的 try 块中复制）
```

#### WP2.2：Hub 侧 trigger_splitter 去重

**问题**：Hub 侧每次收到 5 个并发请求，启动 5 个 splitter 进程。WP2.1 修复后，第一个 splitter 会消费所有 pending，其他 4 个仍会因锁冲突退出。

**方案**：在 `trigger_splitter` 中，如果已有 splitter 在运行（通过 flock 检查），则跳过启动新进程——因为正在运行的 splitter 会消费所有 pending。

**文件**：`scripts/chat_server/services/intent_proposals.py`
**位置**：`trigger_splitter` 函数（L163-234）

**改动**：在 Popen 之前检查锁文件：
```python
# R-DEDUP: 如果已有 splitter 在运行，跳过启动新进程
# 因为正在运行的 splitter 会消费所有 pending 方案
if _is_splitter_running():
    _log.info("splitter 已在运行，跳过 proposal=%s（将排队消费）", proposal_id)
    append_result(
        workspace_root, proposal_id,
        {"status": "queued", "note": "splitter 已在运行，排队消费中"},
    )
    return None

def _is_splitter_running() -> bool:
    """检查 splitter 锁文件是否被占用。"""
    import fcntl
    lock_file = Path.home() / ".ccc" / "intent-splitter.lock"
    try:
        fp = open(lock_file, "w")
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        fp.close()
        return False  # 锁未被占用
    except BlockingIOError:
        return True  # 锁被占用，splitter 正在运行
    except Exception:
        return False
```

---

### WP3：warmup 验证 + 主链路端到端验证

**目标**：构造一个需要真正 opencode 执行的任务，验证 warmup probe 有效性。

#### WP3.1：构造验证方案

**方案**：创建一个新的 stage6-smoke 验证方案，包含一个需要 opencode 执行的简单任务——在 qb workspace 内创建一个测试文件并运行验证。

**文件**：`docs/intent-proposals/stage6-smoke-opencode.md`（新建）

**内容**：
```markdown
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
```

#### WP3.2：验证 warmup 日志

**验证步骤**：
```bash
# 1. 提交方案
python3 scripts/ccc-submit-proposal.py docs/intent-proposals/stage6-smoke-opencode.md --project qb

# 2. 监控 warmup 日志
ssh mac2017 "tail -f ~/.ccc/logs/engine.log | grep -E 'warmup|opencode-exec|opencode'"

# 3. 验证 warmup 在 opencode 执行前被调用
grep 'warmup' ~/.ccc/logs/ccc-engine.log
# 预期："[warmup] ok (rc=0)" 或 "[warmup] timeout (30s)，继续主流程"

# 4. 验证 rc=247 0 次
grep -c 'rc=247' ~/.ccc/logs/engine.log
# 预期：0（warmup 生效后无冷启动超时）
```

#### WP3.3：min-pipeline 下的 warmup 验证

**问题**：min-pipeline 模式下，code review 等任务在 testing 列验收通过后直接跳过 opencode 执行。

**方案**：确保新方案的验收命令需要实际的文件创建和验证，而非纯 existence-only 检查。`cmds_are_existence_only` 会跳过验收只检查文件存在的任务。验收命令应包含实际计算逻辑。

---

### 执行顺序

```
WP1 (主链路修复) ──┐
                   ├─→ 验证（提交 smoke 方案，观察主链路是否走通）
WP2 (并发消费) ────┘
                         
WP3 (warmup 验证) ─────→ 独立验证（构造需要 opencode 执行的任务）
```

WP1 + WP2 在代码修改后同步到 2017 端，提交 smoke 方案验证主链路是否走通。
WP3 在 WP1 验证通过后进行，或在主链路仍走 fallback 时独立验证 warmup。

---

## 四、Assumptions & Decisions

### Assumptions
1. LLM(flash) 经过更清晰的格式提示后，能产出正确的 CHILDREN section
2. LLM 输出的 CHILDREN 内容正确性由 `_validate_epic` 和 `apply_fanout` 保障
3. splitter 锁文件目录有权创建（`~/.ccc/intent-splitter.lock`）

### Decisions
1. **紧缩修复范围**：不修改 LLM 模型选择（仍用 flash），不增加 relay 配置变更
2. **并发消费在 splitter 侧解决**：不在 Hub 侧做复杂队列调度，而是让 splitter 拿到锁后消费所有 pending
3. **warmup 验证独立于主链路**：即使主链路仍走 fallback，warmup 验证可在 opencode 执行时独立观察
4. **不修改 min-pipeline 主逻辑**：只修改验证方案来触发 opencode 执行

---

## 五、Verification Steps

### 5.1 WP1 主链路修复验证

```bash
# 1. 同步代码到 2017
ssh mac2017 "cd ~/program/CCC && git pull origin main"

# 2. 提交一个 smoke 方案
python3 scripts/ccc-submit-proposal.py docs/intent-proposals/stage5-smoke.md --project qb

# 3. 检查 result.jsonl
cat /Users/fan/program/apps/qb/.ccc/intent-proposals/prop-*.result.jsonl
# 预期：fallback=false, claude_session_id 非空
```

### 5.2 WP2 并发消费验证

```bash
# 1. 同时提交 3 个方案
for f in docs/intent-proposals/stage5-t1-write-code.md docs/intent-proposals/stage5-t2-script-seed.md docs/intent-proposals/stage5-t3-bug-fix.md; do
  python3 scripts/ccc-submit-proposal.py "$f" --project qb &
done
wait

# 2. 检查 board（预期 3 个 epic 全部拆卡，0 个 queued）
python3 -c "
from _board_store import FileBoardStore
from pathlib import Path
s = FileBoardStore(Path('/Users/fan/program/apps/qb'))
for col in ['backlog','planned','in_progress','testing','released','abnormal']:
    ts = [t for t in s.list_tasks(col) if 'prop-2026' in t.get('id','')]
    print(f'[{col}] {len(ts)}')
"
```

### 5.3 WP3 warmup 验证

```bash
# 1. 提交 opencode 验证方案
python3 scripts/ccc-submit-proposal.py docs/intent-proposals/stage6-smoke-opencode.md --project qb

# 2. 监控 warmup 日志
ssh mac2017 "grep -E 'warmup|opencode-exec' ~/.ccc/logs/engine.log"
# 预期：含有 "warmup" 日志行

# 3. 验证 rc=247 0 次
ssh mac2017 "grep -c 'rc=247' ~/.ccc/logs/engine.log || echo 0"
# 预期：0
```

### 5.4 回归验证

```bash
# 全量测试
cd ~/program/CCC && python3 -m pytest tests/ -x --tb=short -q
```