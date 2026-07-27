# DEV-PACKET: 013-reviewer-verdict-kpi-honesty

> 复制本文件**全文**发给**个人 Claude Code CLI**（接 Relay `flash`；非 Desktop Agent）。  
> 合入权威 = Cursor。做完提交到指定分支，**不要 push main**。  
> **主题**：金路径 / 门禁诚实（程 B KPI 缩小跑诚实残留）。Ops UI 抛光 **禁止**。

---

## 0. 长任务纪律（Claude Code 主力 · 多 Phase 一次做完）

你是本包的**主力开发**。按 Phase 顺序做完再回报；允许同一分支多 commit。  
每完成一个 Phase：跑该 Phase 验收命令；失败先自修，勿跳 Phase。  
**禁止**只写文档交差；**禁止**改权威/红线/密钥。  
工作节奏建议（自循环，不必等人）：

```text
loop:
  读本包当前 Phase → 改白名单 → py_compile + 相关 pytest →
  git add 白名单 → commit → 进入下一 Phase →
  全部 Phase 绿 → 按 §8 回报
```

若某 Phase 卡住 >2 次失败：在 `RESIDUAL` 写清根因与最小复现，**停**，不要扩大白名单。

---

## 1. 目标（用户可见）

程 B KPI `stress-mx-20260728-kpi-r1` 已 **PASS**，但有诚实缺口：

1. 板面仍可能留 `abnormal` work（reason=`reviewer 未产出 verdict`），而 gate `computed.work_abnormal_n` 却报 **0** → **门禁假绿风险**。  
2. reviewer LLM/`--bg` 路径若未写出 verdict，会进「未产出 verdict」quarantine，而不是先落 **FAIL verdict**（短路径已有确定性 FAIL 写法，LLM 路径要对齐精神）。

做完后：

- 效率报告 / KPI gate 的 `work_abnormal_n` **诚实计入**当前板 `abnormal` 列中、属于本 run 的 work 卡（或文档化明确口径并测锁定）。  
- reviewer 在「无有效 verdict」收尸前，尽量写出 **FAIL verdict 文件**（可 reopen），减少空 reason quarantine。  
- 单测覆盖上述两点。

对应：程 B 残留 · P-C/P-D 门禁诚实。

---

## 2. 分支与提交

- 基线：最新 `origin/main`（应含 `v0.63.0` / `86dd74c` 或更新）
- 分支：`draft/013-reviewer-verdict-kpi-honesty`
- 提交风格：`fix(gate): …` / `fix(reviewer): …` / `test: …`（英文 why）
- **禁止** `git push origin main`；可 `git push -u origin draft/013-reviewer-verdict-kpi-honesty`
- **禁止** `git add -A` / `git add .`；只 add §3 白名单
- 同仓多 agent：**不要** `git add -A`；提交前 `git status` 确认无他人文件

```bash
git fetch origin main
git checkout -B draft/013-reviewer-verdict-kpi-honesty origin/main
```

---

## 3. 白名单（只许改这些）

### 代码 / 测

- `scripts/ccc-stress-efficiency-report.py`
- `scripts/ccc-stress-kpi-gate.py`（若 computed 路径在此）
- `scripts/engine/gates.py`（verdict 门 / quarantine 前写 FAIL 的必要改动）
- `scripts/board/roles/reviewer.py`（LLM 路径无 verdict 时写 FAIL；对齐短路径 `_fail_deterministic` 精神）
- `tests/scripts/test_stress_kpi_gate.py`（若无则新建）
- `tests/scripts/test_reviewer_verdict_failsafe.py`（新建）
- `scripts/tests/test_*.py`（仅当仓内双轨测目录需要镜像时，与 `tests/scripts/` 同内容）

### 文档（薄）

- `docs/briefs/2026-07-28-kpi-shrink-r1-eval.md`（补「修复后」一句，勿改写 PASS 结论）
- `docs/dev-packets/README.md`（本包状态行）
- `docs/briefs/2026-07-27-ccc-production-readiness.md`（程 B 下加一行「013 进行中/已合入」——**仅此一句**，勿改 Layer1 出门句）

### 可选（仅当测需要 fixture）

- `tests/scripts/fixtures/**`（新建小 fixture，禁止塞业务仓）

---

## 4. 黑名单（碰了就停）

- `docs/product/loop-engineer-authority.md`
- `.cursor/rules/loop-engineer-consensus.mdc`
- `references/red-lines.md`
- `references/stress-kpi-scorecard.json`（门槛数字 **勿改**；诚实计数不等于放宽门槛）
- `VERSION` / `CHANGELOG.md` / `docs/releases/**`（发版留给 Cursor）
- `relay/**`、`~/.ccc/**`、launchd/plist、密钥
- Desktop / Swift / Ops UI / SPA
- 业务仓 `/Users/fan/program/apps/**`（本包不改业务树）
- 任意未列路径

---

## 5. 现状锚点

| 锚点 | 说明 |
|------|------|
| KPI brief | `docs/briefs/2026-07-28-kpi-shrink-r1-eval.md` §诚实残留 #2 |
| Gate 逻辑 | `scripts/ccc-stress-kpi-gate.py` + efficiency report computed |
| Quarantine 文案 | `scripts/engine/gates.py` ≈528：`reviewer 未产出 verdict` |
| 短路径已正确 | `scripts/board/roles/reviewer.py` ≈190–218：确定性路径必须写 FAIL verdict，禁止静默 |
| Scorecard | `references/stress-kpi-scorecard.json`：`work_abnormal_n` ≤1 |
| 版本 | `VERSION` = v0.63.0（本包不 bump） |

---

## 6. 实现步骤（Phase）

### Phase A — 摸清 computed 口径（只读 + 最小复现测）

1. 读 `ccc-stress-efficiency-report.py` / `ccc-stress-kpi-gate.py`：`work_abnormal_n` 从何而来。  
2. 写失败测（红）：构造临时 board（tmp_path）含 1 张 `abnormal` work（id 带 run 前缀），断言 computed ≥1 **或** 若设计是「只计未 ui_hidden 且未 quarantine」则测锁定该口径并在 brief 写清。  
3. **目标**：消灭「板上有 abnormal、gate 报 0」的默契漏洞（除非文件已 `ui_hidden` / 明确排除规则）。

### Phase B — 修效率报告 / gate 计数

1. 让 `computed.work_abnormal_n` 反映：**本 run 相关**、**未隐藏**的 abnormal work 数。  
2. 勿把已 `ui_hidden` / 非本 run 的历史 abnormal 算进来（避免永久污染）。  
3. run 前缀约定：效率 JSON 的 `run` / dispatch slug（如 `stress-mx-20260728-kpi-r1`）匹配 task_id 前缀。  
4. 单测绿。

### Phase C — reviewer 无 verdict → 先写 FAIL

1. 在 `gates.py` 进入 `reviewer 未产出 verdict` quarantine **之前**：若 verdict 文件不存在或无效，调用小 helper 写：

```markdown
# <tid> Verdict

**Verdict:** FAIL

**Category:** fixable

**Reason:** reviewer_produced_no_verdict
```

2. 或在 `reviewer.py` LLM 结束路径保证：任何非超时退出也落 verdict（优先与现有 `_fail_deterministic` 共用格式）。  
3. **不要**改变 PASS 判定；只补「空 verdict」收尸。  
4. 单测：模拟无 verdict → 调用后文件存在且含 `FAIL`；再 quarantine 文案可仍保留或改为指向 FAIL（二选一，文档写清）。

### Phase D — 文档与回报

1. 更新 `2026-07-28-kpi-shrink-r1-eval.md`：残留 #2 加「013 修复口径：…」。  
2. `docs/dev-packets/README.md` 加本包行（状态：`draft`）。  
3. production-readiness 程 B 下加一行 `- [ ] 013 …` 或完成后 `[x]`（由你标 draft；Cursor 合入后再勾）。  
4. 按 §8 回报。

---

## 7. 验收（必须跑）

```bash
# 语法
python3 -m py_compile \
  scripts/ccc-stress-efficiency-report.py \
  scripts/ccc-stress-kpi-gate.py \
  scripts/engine/gates.py \
  scripts/board/roles/reviewer.py

# 单测（按你实际新建/改动的文件名调整 -k）
PYTHONPATH=scripts pytest \
  tests/scripts/test_stress_kpi_gate.py \
  tests/scripts/test_reviewer_verdict_failsafe.py \
  tests/scripts/test_long_lived_session.py \
  -q --tb=short

# 若改了 gates 通用测
PYTHONPATH=scripts pytest tests/scripts/ -q --tb=line -k "verdict or abnormal or kpi_gate" 

# 禁止
# - 改 scorecard 门槛数字来「刷绿」
# - 对 ccc-demo 真板清卡当「修复」（清场不是本包）
```

期望：相关测全绿；`git status` 仅白名单改动。

---

## 8. 做完回报（固定格式）

```
BRANCH: draft/013-reviewer-verdict-kpi-honesty
FILES:
- …
TESTS:
- … → pass/fail
COMMITS:
- <sha> <subject>
RESIDUAL:
- …
HOW_TO_REVIEW:
- git fetch && git checkout draft/013-reviewer-verdict-kpi-honesty
- PYTHONPATH=scripts pytest …（同上）
```

---

## 9. 给转发者的一句话

把本文件从标题到 §8 整份贴进 Claude Code；做完把 `BRANCH` + `git log --oneline origin/main..HEAD` + diff 统计发回 Cursor 审合入。
