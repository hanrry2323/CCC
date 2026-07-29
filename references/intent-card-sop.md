# 转意图卡 SOP（Agent · 失败案例驱动）

> **谁用**：Desktop App Agent（快捷「转意图卡」/ `ccc-transfer` 契约块）。  
> **目的**：人认白话意图后，起草**精准意图卡**；`transfer_gate` 绿才自动进代办（Engine 开工）。禁止糊卡进 OpenCode。  
> **SSOT 链**：本文件 → `hub_voice`「转意图卡纪律」→ `QuickPrompts.finalize`（UI 名「转意图卡」）→ `transfer_gate` → qb `transfer_playbook`。  
> **旧名**：`finalize-transfer-sop.md`（重定向到本文）。

---

## 0. 三角色（硬）

| 角色 | 权责 |
|------|------|
| **人** | 唯一**发起**「转意图卡」；只审白话路线：整条计划要走到哪、每步怎样算完；飞轮推到右栏的下一意图仍须人点转才进代办 |
| **Agent** | **架构师**：人触发后把已排的**系列开发计划**落成**整条意图卡链**（多卡优先）；未收敛拒转；gate 红按 `fix_hint` 改卡 |
| **系统** | `transfer_gate` **仅绿**才 auto 进代办；空闲飞轮自动写下一 L1 `planned`（不写 backlog） |

**转意图卡 ≠ 定代办**。代办 = Engine 弹药；卡错则全错。

**架构师口径**：对齐基线先排 3～7 步系列计划；转意图卡 = 整条计划入链，禁止只落「当前一个小功能」。  
**一次点透 → 整条链（1）**：系列 ≥2 步 → 必须多块 `ccc-transfer` / `cards:[]`；禁止一轮一张糊大卡。  
**飞轮空闲（3）**：板空闲且无 planned → 系统从规划文推下一产品意图到右栏；进代办仍须人点「转意图卡」。

---

## 1. 收敛门（未谈妥不准转）

人点「转意图卡」时自检；不满足则**只回白话缺什么**，不写 L1、不入队：

1. 要做成什么（可命名的一个变化）是否已用白话对齐  
2. 怎样算验收过（人话）是否对齐  
3. 是否仍在「多路线未选」——未选则禁止转  

战略讨论优先；可查 HP 知识库 / 社区资料。**禁止**未收敛自转、空闲 invent、开场运维说教。

---

## 2. 起草前（静默 · 勿写入用户正文）

1. `hub_board` + `hub_git`：板堵 → `hub_repair(clear_blockers)`；仅业务脏 / 真在飞冲突 → `feasibility=blocked`（或人 override 记 `human_note`）。
2. `hub_modules` → `hub_locate` / `hub_file`：scope 路径真实；**禁止**编造模块存在性。
3. 读 digest「近期定卡教训」+ qb 定卡反模式；耗尽卡先 `failure_pack` / `optimize_hint`，禁止原样重下。
4. 对齐 L1：`title`/`goal` 对齐未完意图原文，或显式 `supersede_goals` / `abandon_prior`（防 `intent_not_stable`）。

---

## 3. 契约硬预算（过门 + 可执行）

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
| 同卡堆 **后期意图**探针（如 A 改 unit，验收却跑 `paper_intent_probe` / 60s e2e） | `acceptance_cmd_failed` / hang |
| 同一命令复制多遍 + 再加弱探针 | 门禁噪 / salvage 拒 |
| 排除路径写进 acceptance | `acceptance_paths_not_in_commit` |
| 裸 `python`（无 venv / 无 DRY_RUN） | 环境漂移 |

**规则**：下一张 L1 目标（paper 60s / Layer2）**另开意图卡**，禁止塞进本卡验收「顺便做」。大方案拆 **多张意图卡**，禁止一卡梭。

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

- **必须**有 `## 验收`（与 acceptance 同向）。
- goal 要 CLOSE / 净 edge → plan **禁止**写「交给上层 / 只 OPEN」（`plan_goal_conflict`）。

---

## 4. 两段落盘（系统推进 · 人不守夜）

1. **转意图卡成功** = 写/更新 L1 `planned`（右栏意图卡链）。此时 **Engine 尚未消费**——**不算完成**。
2. **进代办** = 同卡契约 `validate_transfer_payload` **绿** → 自动 transfer → backlog epic + **wake Engine**。  
   - Desktop 解析 `ccc-transfer` 后自动 L1→gate→outbox；若 Agent **只写了右栏 L1**，Hub `POST /transfer/promote-planned` 兜底推进。
   - **红**：卡留意图层；按 `fix_hint` 改卡再检；**零 OpenCode**。  
   - 改卡若动到「要做成什么」的白话含义 → **必须再用人话问人**，不得静默改意图硬过门。
3. **谁推动**：人点「转意图卡」= 唯一发起；之后 **系统**（Desktop promote / Hub promote-planned / transfer wake）负责进代办与拉起 Engine。**禁止**让人盯右栏或手动「确认进代办」当主路径。
4. **Agent 硬完成**：可见答复里出可过门的 `ccc-transfer`；禁止只 mind 写 L1 交差；禁止 `clear_blockers`/归档话术冒充已开工。

---

## 5. 对用户输出

1. 白话 **2～4 句**：做什么、怎么算验收过、拆成几张意图（若多张）。
2. **恰好一个** ` ```ccc-transfer` **块**（字段齐；内部契约名仍兼容）；禁止再问「要不要入队」。
3. 正文禁平台黑话；路径/命令只进块内。

---

## 6. 失败回流

| 现象 | 怎么改 |
|------|--------|
| Gate 红 | 读 `errors[].fix_hint`；**必读** L1 digest「近期定卡教训」/`transfer_lessons`（validate 与投递红均写）；本机 `transfer-receipts.json` 可有 `status=rejected`；改卡再出块（意图层停留，**禁止声称已进代办**） |
| hang / `acceptance_cmd_failed` | 砍 acceptance 到 1～2 条本卡 pytest；挪走 e2e/probe |
| 耗尽 | `post-exhaust-epic-optimize-sop`：归档旧卡 → 按桶缩小 → **新意图卡**（须人再点转） |
| 假绿 / revert 来回 | 禁「先 revert 再 restore」当修法；验绿即停并 commit |

---

## 7. qb 对照案例（2026-07-29）

**坏卡**（`p0-momentum-cost-edge-close-5f90684d`）：acceptance 同时含  
`test_momentum_fees` + `test_templates` + **`paper_intent_probe`** + 多条 `test -f` → salvage 拒 / hang。

**好卡**：goal=净 edge+CLOSE+单测；acceptance **仅**  
`.venv/bin/python -m pytest -q tests/unit/test_momentum_fees.py`  
（可选再加一条同意图 corner 测）；paper 探针留给下一张意图卡。
