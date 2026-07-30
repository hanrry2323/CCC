# 意图卡 SOP（架构师开发伙伴 · 自动投链）

> **谁用**：Desktop App Agent（理解意图后自动出 `ccc-transfer`；**无**「转意图卡」按钮）。  
> **目的**：架构师理解意图后，起草**精准意图卡链**；`transfer_gate` 绿才自动进代办。禁止糊卡；失败后读证据优化改卡并**再自动投链**。  
> **身份**：[`docs/product/desktop-agent-identity.md`](../docs/product/desktop-agent-identity.md)  
> **全流程**：[`intent-chain-dev-sop.md`](intent-chain-dev-sop.md)  
> **SSOT 链**：本文件 → `hub_voice` → sidecar 注入 → `transfer_gate`。  
> **旧名**：`finalize-transfer-sop.md`（重定向到本文）。

---

## 0. 三角色（硬 · 2026-07-30）

| 角色 | 权责 |
|------|------|
| **人** | 聊清「要做成什么 / 怎样算完」；可选「对齐基线」「扫风险」；**不**靠点「转意图卡」按钮发起 |
| **Agent** | **高级智能开发伙伴 · 架构师**：分析→架构→意图→**自动**落成整条意图卡链；入队后读测/失败自动纠偏；耗尽优化新卡并**自动再投**；gate 红按 `fix_hint` 改卡 |
| **系统** | `transfer_gate` **仅绿**才 auto 进代办；Engine 跑写码/审测；空闲飞轮写下一 L1 `planned`（不写 backlog；禁 invent） |

**出契约 ≠ 定代办**。代办 = Engine 弹药；卡错则全错。  
**发起权 = Agent 在意图收敛后自动投链**（用户口述「开发/下达/跑通」等同触发）。  
**仍禁 invent**：无用户意图时不得自造 backlog。

**架构师口径**：对齐基线先排 3～7 步系列计划；投链 = 整条计划入链，禁止只落「当前一个小功能」。  
**一次投透 → 整条链**：系列 ≥2 步 → 必须多块 `ccc-transfer` / `cards:[]`；禁止一轮一张糊大卡。  
**飞轮空闲**：板空闲且无 planned → 系统从规划文推下一产品意图到右栏；**进代办须 Agent 再理解并自动投**（仍禁 invent 直灌）。  
**失败纠偏**：读 `failure_pack` / verdict → 优化新意图卡并自动投；禁止只归档交差。

---

## 1. 收敛门（未谈妥不准投）

自检；不满足则**只回白话缺什么**，不写 L1、不入队：

1. 要做成什么（可命名的一个变化）是否已用白话对齐  
2. 怎样算验收过（人话）是否对齐  
3. 是否仍在「多路线未选」——未选则禁止投  

战略讨论优先；可查 HP / 社区。**禁止**未收敛自转、空闲 invent、开场运维说教。

---

## 2. 起草前（静默 · 勿写入用户正文）

1. `hub_board` + `hub_git`：板堵 → `hub_repair(clear_blockers)`；仅业务脏 / 真在飞冲突 → `feasibility=blocked`（或人 override 记 `human_note`）。
2. `hub_modules` → `hub_locate` / `hub_file`：scope 路径真实；**禁止**编造模块存在性。
3. 读 digest「近期定卡教训」+ qb 定卡反模式；耗尽卡先 `failure_pack` / `optimize_hint`，禁止原样重下。
4. 对齐 L1：`title`/`goal` 对齐未完意图原文，或显式 `supersede_goals` / `abandon_prior`。
5. scope **禁止**敏感路径（`.env` / credentials / `control.json`）——gate 码 `sensitive_scope`。

---

## 3. 契约硬预算（过门 + 可执行）

| 项 | 硬上限 | 失败若违反 |
|----|--------|------------|
| 意图 | **1** 个可命名变化 | hang / 扇出糊成多 phase |
| work / phase | **1** work · **1** phase（默认） | `plan_scope_too_wide` / hang |
| scope | **≤5** 文件或同顶层 1 目录；禁敏感路径 | hang / `sensitive_scope` |
| acceptance | **1～3** 条强探针，**优先 1～2** | `acceptance_cmd_failed` / hang |
| title | ≤80 字可执行中文 | 软裁 / 难对齐 L1 |
| complexity | 默认 `medium`；多步回归禁 `small` | 门禁误跳路径 |

### acceptance 白名单（强）

- `.venv/bin/python -m pytest -q <本卡测试路径>`
- `DRY_RUN=true .venv/bin/python <本卡脚本> …`
- `python3 -c "…assert…"`（短、可重放）

### acceptance 黑名单（必删）

| 反模式 | 真实失败 |
|--------|----------|
| `test -f …` / 散文「写好了」 | `acceptance_weak`；假绿 |
| 同卡堆 **后期意图**探针（paper / 60s e2e） | `acceptance_cmd_failed` / hang |
| 同一命令复制多遍 + 再加弱探针 | 门禁噪 / salvage 拒 |
| 排除路径写进 acceptance | `acceptance_paths_not_in_commit` |
| 裸 `python`（无 venv / 无 DRY_RUN） | 环境漂移 |

**规则**：下一张 L1 目标另开意图卡。大方案拆 **多张意图卡**，禁止一卡梭。

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

---

## 4. 两段落盘（系统推进 · 人不守夜）

1. **意图卡落盘** = 写/更新 L1 `planned`（右栏）。Engine 尚未消费——**不算完成**。
2. **进代办** = 契约 `validate_transfer_payload` **绿** → 自动 transfer → backlog + **wake Engine**。  
   - Desktop 解析 `ccc-transfer` 后 **自动** L1→gate→outbox（不等人点按钮）。  
   - 若 Agent 只写了右栏 L1，Hub `POST /transfer/promote-planned` 兜底。  
   - **红**：卡留意图层；按 `fix_hint` 改卡再投；**零 OpenCode**。  
   - 改卡若动到白话意图含义 → **必须再用人话问人**。
3. **谁推动**：Agent 理解后出契约 = 发起；之后 **系统** promote / wake。**禁止**让人盯右栏或点「转意图卡」。
4. **Agent 硬完成**：可见答复里出可过门的 `ccc-transfer`；禁止只 mind 写 L1 交差。

---

## 5. 对用户输出

1. 白话 **2～4 句**：做什么、怎么算验收过、拆成几张意图。
2. 一个或多个 ` ```ccc-transfer` **块**（字段齐）；禁止再问「要不要入队」。
3. 正文禁平台黑话；路径/命令只进块内。

---

## 6. 失败回流

| 现象 | 怎么改 |
|------|--------|
| Gate 红 | 读 `errors[].fix_hint` + digest 教训；改卡再出块（**禁止声称已进代办**） |
| hang / `acceptance_cmd_failed` | 砍 acceptance 到 1～2 条本卡 pytest；挪走 e2e/probe |
| 耗尽 | `post-exhaust-epic-optimize-sop`：归档 → 优化新卡 → **自动再投** |
| 假绿 / revert 来回 | 禁「先 revert 再 restore」；验绿即停并 commit |
| dirty_block 噪音 | 见 `commit-folder-hygiene-sop`；不当业务失败改意图 |

---

## 7. qb 对照案例（2026-07-29）

**坏卡**：acceptance 同时含 unit + `paper_intent_probe` + `test -f` → hang。  
**好卡**：acceptance **仅** `.venv/bin/python -m pytest -q tests/unit/test_momentum_fees.py`。

**2026-07-30 dirty_block 真案**：`scripts-b5-metrics-…-w1` 代码已绿且有 task_id commit，但仓根 `Author:` 空文件 + `dashboard/` 残留触发假 dirty_block → **程序门禁已修**（existing commit + outside junk = 不挡）；Agent 侧勿把此类当改意图。
