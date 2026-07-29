# 定稿转任务 SOP（Agent · 失败案例驱动）

> **谁用**：Desktop App Agent（定稿快捷指令 / `ccc-transfer`）。  
> **目的**：契约一次过门，Engine 能扇出、能验绿；禁止「写得热闹、跑不下去」。  
> **SSOT 链**：本文件 → `hub_voice`「定大卡纪律」→ `QuickPrompts.finalize` → `transfer_gate` → qb `transfer_playbook`。

---

## 0. 一句话

**一张卡 = 一个可证明的意图变化**；验收只放**能在本卡 scope 内 2 分钟内重放**的强探针。

---

## 1. 定稿前（静默 · 勿写入用户正文）

1. `hub_board` + `hub_git`：板堵 → `hub_repair(clear_blockers)`；仅业务脏 / 真在飞冲突 → `feasibility=blocked`（或人 override 记 `human_note`）。
2. `hub_modules` → `hub_locate` / `hub_file`：scope 路径真实；**禁止**编造模块存在性。
3. 读 digest「近期定卡教训」+ qb 定卡反模式；耗尽卡先 `failure_pack` / `optimize_hint`，禁止原样重下。
4. 对齐 L1：`title`/`goal` 对齐未完意图原文，或显式 `supersede_goals` / `abandon_prior`（防 `intent_not_stable`）。

---

## 2. 契约硬预算（过门 + 可执行）

| 项 | 硬上限 | 失败若违反 |
|----|--------|------------|
| 意图 | **1** 个可命名变化 | hang / 扇出糊成多 phase |
| work / phase | **1** work · **1** phase（默认） | `plan_scope_too_wide` / hang |
| scope | **≤5** 文件或同顶层 1 目录 | hang / 串行锁 |
| acceptance | **1～3** 条强探针，**优先 1～2** | `acceptance_cmd_failed` / hang |
| title | ≤80 字可执行中文 | 软裁 / 难对齐 L1 |
| complexity | 默认 `medium`；多步回归禁 `small` | 门禁误跳路径 |

### acceptance 白名单（强）

- `.venv/bin/python -m pytest -q <本卡测试路径>`
- `DRY_RUN=true .venv/bin/python <本卡脚本> …`（脚本须在本卡 scope 内或本卡新建）
- `python3 -c "…assert…"`（短、可重放）

### acceptance 黑名单（必删）

| 反模式 | 真实失败 |
|--------|----------|
| `test -f …` / 散文「写好了」 | `acceptance_weak`；假绿 |
| 同卡堆 **后期意图**探针（如 A 改 unit，验收却跑 `paper_intent_probe` / 60s e2e） | `acceptance_cmd_failed` / hang（qb `…5f90684d`） |
| 同一命令复制多遍 + 再加弱探针 | 门禁噪 / salvage 拒 |
| 排除路径写进 acceptance | `acceptance_paths_not_in_commit` |
| 裸 `python`（无 venv / 无 DRY_RUN） | 环境漂移 |

**规则**：下一张 L1 目标（paper 60s / Layer2）**另开卡**，禁止塞进本卡验收「顺便做」。

### plan_md 正形

```markdown
# <短标题>
## 目标
<与 goal 同向一句>
## 范围
- path/a.py
- path/b_test.py
## 步骤
1. <唯一实现动作 · 勿 Step1–6>
## 验收
- <与 acceptance[0] 相同的那条命令>
## 禁止
- <勿改清单 · 排除路径写这里>
```

- **必须**有 `## 验收`（与 acceptance 同向）；草稿缺节会被拒（若 acceptance 已强，Hub 可重建，但仍应写齐）。
- goal 要 CLOSE / 净 edge → plan **禁止**写「交给上层 / 只 OPEN」（`plan_goal_conflict`）。

---

## 3. 对用户输出

1. 白话 **2～4 句**：做什么、怎么算验收过、是否立刻转。
2. **恰好一个** ` ```ccc-transfer` **块**（字段齐）；禁止再问「要不要入队」。
3. 正文禁平台黑话；路径/命令只进块内。

---

## 4. 失败回流（定稿后仍挂）

| 现象 | 定稿怎么改 |
|------|------------|
| Gate 4xx | 读 `errors[].fix_hint` + code，改卡再出块 |
| hang / `acceptance_cmd_failed` | 砍 acceptance 到 1～2 条本卡 pytest；挪走 e2e/probe |
| 耗尽 | `post-exhaust-epic-optimize-sop`：归档旧卡 → 按桶缩小 → 新 `ccc-transfer` |
| 假绿 / revert 来回 | 禁「先 revert 再 restore」当修法；验绿即停并 commit |

---

## 5. qb 对照案例（2026-07-29）

**坏定稿**（`p0-momentum-cost-edge-close-5f90684d`）：acceptance 同时含  
`test_momentum_fees` + `test_templates` + **`paper_intent_probe`** + 多条 `test -f` → Engine salvage 拒 / hang。

**好定稿**：goal=净 edge+CLOSE+单测；acceptance **仅**  
`.venv/bin/python -m pytest -q tests/unit/test_momentum_fees.py`  
（可选再加一条同意图 corner 测）；paper 探针留给 L1 下一目标另卡。
