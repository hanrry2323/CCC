# DEV-PACKET: golden-path-kb-script-seed

> **大包长任务**：一次会话做完下方全部 Phase，只回报一次。  
> 合入权威 = **Cursor**。做完只提交到指定分支，**不要 push main**。  
> 先：`git checkout main && git pull --ff-only`，再开分支。  
> 发给**个人 Claude Code CLI**（Relay `flash` 即可；非 Desktop Agent；非 Cursor Cloud 主路径）。  
> 主题：Layer1 金路径残账（kb 同 tick / 列迁移 / script_seed 勿抢 opencode 戳记）。**不碰** relay / Ops UI / OpenCode 本机配置。

## 1. 总目标（用户可见）

金路径卡进 `verified` 后不再靠人工 `kb_role()` 才 `released`；审测 pullback 不再刷「拒绝迁移: verified → testing」；`executor=opencode` 的 docs 戳记卡不再被 `script_seed` 写成 `PENDING` + `paper_intent_probe` 假 commit。

对应证据断点：[`docs/briefs/2026-07-27-golden-path-evidence.md`](../briefs/2026-07-27-golden-path-evidence.md) v2「下一程」前三条（OpenCode 模型切 Zen **不在本包**）。

做完后定向 pytest 全绿；Cursor 合入 + 2017 Engine kickstart 后再证一笔 epic（本包不跑真机）。

## 2. 分支与提交

- 分支：`draft/golden-path-kb-script-seed`
- **可以多个 commit**（按 Phase），会话结束时分支干净可审
- 建议 commit messages：
  - `fix(engine): allow verified→testing pullback; kb every tick`
  - `fix(script_seed): never hijack explicit opencode docs stamps`
  - `test: kb move + script_seed opencode guard`
- 禁止 `git push origin main`；可不 push，或 `git push -u origin draft/golden-path-kb-script-seed`
- **禁止** `git add -A` / `git add .`；每次只 add 本 Phase 白名单文件

## 3. 白名单（整包允许）

- `scripts/_board_store.py`（仅 `COLUMN_TRANSITIONS` / `move_task` 相关注释与白名单）
- `scripts/engine/workspace.py`（`_ensure_task_in_testing`）
- `scripts/engine/gates.py`（若需在 testing 门禁收口后触发 kb / 调用辅助）
- `scripts/ccc-engine.py`（verified→kb 调度：每 tick，勿仅 `% 6`）
- `scripts/board/roles/script_seed.py`（`looks_like_intent_probe_seed` / `should_use_script_seed`）
- `tests/scripts/test_script_seed.py`
- `tests/scripts/test_board_store.py`（若已有 move 测；可新建下列之一）
- `tests/scripts/test_engine_kb_gate.py`（**可新建**）
- `tests/scripts/test_ensure_testing_column.py`（**可新建**）

## 4. 黑名单（碰了就停）

- `docs/product/loop-engineer-authority.md`
- `references/red-lines.md`
- `~/.ccc/**`、真密钥、plist、`relay/upstreams.json`
- `relay/**`（中转站已另会话）
- `desktop/**`、Ops SPA 抛光
- `scripts/board/roles/kb.py` 业务逻辑大改（本包只要求 **被调用到**；除非最小接线必须）
- 其它未列路径

## 5. 现状锚点（必读再改）

### 5.1 verified→testing 被拒

[`scripts/_board_store.py`](../../scripts/_board_store.py) `COLUMN_TRANSITIONS`：

```python
"testing": ["in_progress", "abnormal", "planned"],  # 缺 verified
```

[`scripts/engine/workspace.py`](../../scripts/engine/workspace.py)：

```python
def _ensure_task_in_testing(store, tid):
    if _find_task_column(store, tid) == "verified":
        store.move_task(tid, "verified", "testing")  # 被拒 → 日志噪音
```

doc_only reviewer 常已把卡挪到 `verified`，随后 gate 仍调 pullback → 刷屏「拒绝迁移」。

### 5.2 kb 滞后

[`scripts/ccc-engine.py`](../../scripts/ccc-engine.py)：

- **每 tick** 跑 testing 门禁（~2593）
- **`verified → kb` 主要在 `iteration % 6 == 0` 块**（~2630）+ idle 块（~2699）
- 实战：卡已在 `verified`，Engine 深睡/未进 `% 6` → 需人工 `kb_role()`

**目标**：testing 门禁同一调度粒度下，**每个 tick** 对有 `verified` 的 workspace 调用 `_run_verified_kb_gate`（可与 idle 路径并存，注意幂等）。

### 5.3 script_seed 抢 opencode

[`scripts/board/roles/script_seed.py`](../../scripts/board/roles/script_seed.py)：

```python
def should_use_script_seed(...):
    if not looks_like_intent_probe_seed(...):
        return False
    exec_id = ...
    if exec_id in ("python", "auto", "cli", "opencode", ""):  # ← opencode 被当成可 seed
        return True
```

docs-only scope 已有拒绝逻辑；但若 **phases scope 为空** / blob 误命中 marker，仍可能 seed。  
金路径 v2 曾出现：`feat(...): seed paper_intent_probe via script_seed` 而意图是 docs 戳记。

**目标**：

1. `executor == "opencode"` **默认不走** script_seed，除非 tags 显式 `script-seed` / `intent-probe-seed`（保留纸面探针压测路径）。
2. 标题/描述含「文档戳记」「金路径」「GOLDEN_PATH」等 → `looks_like_intent_probe_seed` 直接 False。
3. 既有 docs-only scope 拒绝保持；`no-script-seed` 子串假阳修复保持。

相关证据：[`docs/briefs/2026-07-27-golden-path-evidence.md`](../briefs/2026-07-27-golden-path-evidence.md)。

---

## Phase A — 列迁移 + 每 tick kb（约 60–120 分钟）

**做：**

1. **`COLUMN_TRANSITIONS["testing"]`** 增加 `"verified"`，注释写清：reviewer 提前 verified 时 gate 可拉回跑 tester/pytest。  
2. **`_ensure_task_in_testing`**：若 `move_task` 失败（或仍不在 testing），打 **debug/warning 一次** 即可，勿死循环；成功路径要真能从 verified 回到 testing。  
3. **`ccc-engine.py`**：在「每 tick testing 门禁」循环之后（与 `% 6` 无关），对每个 workspace：若 `list_tasks("verified")` 非空 → `_run_verified_kb_gate(ws)`。  
   - `% 6` 里原有 kb 调用可保留（双调无害）或删掉避免重复日志——任选，优先 **少噪音**。  
   - idle 路径 kb **保留**。  
4. 不要改 kb_role 的 VERSION bump 语义。

**Phase A 自检：**

```bash
python -m py_compile scripts/_board_store.py scripts/engine/workspace.py scripts/engine/gates.py scripts/ccc-engine.py
# 见 Phase C 单测
```

**建议单测行为（可放 Phase C 文件）：**

- store：`verified → testing` `move_task` 返回 True。  
- （可选）mock：testing 门禁后 engine 路径会调 kb——若难测 engine 主循环，至少测 transitions + `_ensure_task_in_testing` 真移动文件。

---

## Phase B — script_seed 勿抢 opencode 戳记（约 45–90 分钟）

**做：**

1. 改 `should_use_script_seed`：  
   - `executor` 规范化后为 `opencode` 时，**仅当** tags 含 `script-seed` 或 `intent-probe-seed` 才 True；否则 False。  
   - `python` / `auto` / `cli` / 空 仍可在 `looks_like_intent_probe_seed` 为 True 时 seed。  
2. 改 `looks_like_intent_probe_seed`：若 title/description/note 命中文档戳记类（建议子串）：`文档戳记`、`金路径`、`GOLDEN_PATH`、`golden-path`、`golden_path` → 直接 False（在强 marker 之前）。  
3. **不要**破坏：带 `tags: ["script-seed"]` 的纸面探针 + `executor=opencode` 仍 True（现有 `test_should_use_script_seed_for_paper_probe` 首断言）。  
4. 扩展 `tests/scripts/test_script_seed.py`：  
   - opencode + docs stamp 标题 + **无** script-seed tag + scope 暂空 → False  
   - opencode + 纸面标题 + script-seed tag → True（已有）  
   - opencode + 纸面标题 + **无** tag + scope=`scripts/paper_intent_probe.py` → **False**（新口径：显式 opencode 须 tag 才 seed；纸面机械卡应 transfer 为 python）

**注意**：第 4 条最后一项会改变「opencode + paper scope 无 tag」行为——这是刻意的：transfer 已把真纸面探针 coerce 成 `python`（见同文件 `test_transfer_coerce_probe_to_python`）。若你发现压测矩阵依赖「opencode+paper 无 tag 仍 seed」，在 `RESIDUAL` 写明，并改为「无 tag 但 scope 全是 paper_intent_probe.py 仍 True」的折中——**优先写进回报让 Cursor 裁夺**，默认按「opencode 无 tag → 不 seed」。

**Phase B 自检：**

```bash
python -m py_compile scripts/board/roles/script_seed.py
pytest tests/scripts/test_script_seed.py -q --tb=short
```

---

## Phase C — 回归测与整理（约 30–60 分钟）

**做：**

1. 补齐 Phase A/B 单测文件（白名单内新建 OK）。  
2. 跑：

```bash
python -m py_compile \
  scripts/_board_store.py \
  scripts/engine/workspace.py \
  scripts/engine/gates.py \
  scripts/ccc-engine.py \
  scripts/board/roles/script_seed.py

pytest tests/scripts/test_script_seed.py \
  tests/scripts/test_acceptance_gate.py \
  tests/scripts/test_board_store.py \
  -q --tb=short

# 若新建了下列文件则一并跑：
# tests/scripts/test_engine_kb_gate.py
# tests/scripts/test_ensure_testing_column.py
```

3. 确认 **未改** `_acceptance_gate` dirty-vs-commit 行为（已有测须仍绿）。  
4. `git status`：仅白名单文件；无密钥、无 `opencode_slots.json` 等噪音。

---

## 8. 做完回报（固定格式）

```
BRANCH: draft/golden-path-kb-script-seed
FILES:
- …
COMMITS:
- …
TESTS:
- py_compile … → pass/fail
- pytest … → pass/fail（贴摘要）
BEHAVIOR:
- verified→testing: …
- kb every tick: …
- opencode without script-seed tag: …
RESIDUAL:
- …
```

把以上块 + `git log main..HEAD --oneline` + 必要时 `git diff main...HEAD --stat` 发回 **Cursor** 会话审合入。

---

## 非目标（本包禁止发散）

- 改 2017 `~/.config/opencode` / xfyun→Zen（Cursor 双机配置）
- relay cooldown / fail-open
- Desktop / Hub SPA
- 权威文档大段重写
- 在业务仓 qb 真跑 epic（合入后由 Cursor 证）
