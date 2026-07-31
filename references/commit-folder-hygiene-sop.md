# Commit 与文件夹卫生 SOP（Agent / Engine / Claude/OpenCode）

> **权威**：`docs/product/loop-engineer-authority.md`「编排自愈硬指标」+ 同仓多 agent 纪律  
> **关联**：[`abnormal-solve-sop.md`](abnormal-solve-sop.md) · DoD=`scripts/_task_commit.py` · 脏树分类=`scripts/_project_baseline.py`  
> **对象**：Desktop Agent 定稿/解释板况 · Engine OpenCode 落盘 · 开发工具（Claude/OpenCode）合入平台时对齐  
> **禁止**：把「脏树很大」当成业务失败结案；禁止 `git add -A` / `git add .`；禁止卫生 epic 当主业；禁止 invent

---

## 一句话

**Commit 卫生** = 只提交本任务白名单、message 含 `task_id`（+`phase`）、噪音不进业务 commit。  
**文件夹卫生** = `.ccc/` 与 lessons 是编排产物；能挡板的只有**真业务脏**与**真在飞**，不是「文件很多」。

---

## A. Commit 卫生（硬）

### A1. 什么叫合格 commit

| 项 | 要求 |
|----|------|
| 范围 | **只** plan/phase `scope`（或 result.`wrote`）里的路径 |
| message | **必须**含 `task_id`；有 phase 时含 `phase=N` |
| 禁止 | `git add -A` / `git add .`；把无关 `.ccc/board|stats|quarantines` 打进业务 commit |
| 已绿 | 验收命令已全绿且 scope 无待改 → **立即**按上表 commit（或确认已有含 task_id 的 commit）并结束；**禁止**继续重构导致 hang |

### A2. 谁负责 commit（分责 · 2026-07-30）

| 对象 | 谁 | 职责 |
|------|-----|------|
| **业务源码 + 本卡测试** | OpenCode 优先；**Engine DoD** `ensure_task_commit` 兜底 | 只 stage scope；message 含 `task_id`；写完即停 |
| **文本 / 脑包 / 规划叙述** | **对话 Agent**（Hub mind；本机 CCC 可写平台文档） | **不**经 OpenCode；**不**为纯文案开产线卡 |
| **`.ccc` / lessons 噪音** | 无人「业务 commit」 | 留盘；`ccc_hygiene` **不挡** ready |
| Desktop Agent | 不手搓业务仓 git | dirty_block → 本文 + abnormal-solve；禁卫生 epic |
| Claude/OpenCode | 只合入 **CCC 平台仓** | 业务仓不直写 |

评估：[`docs/briefs/2026-07-30-granularity-text-code-commit.md`](../docs/briefs/2026-07-30-granularity-text-code-commit.md)。

### A3. 脏树三分法（解释板况时必须用）

| `dirty_kind` | 含义 | 是否挡新产品 epic / ready |
|--------------|------|---------------------------|
| `clean` | 无脏 | 否 |
| `ccc_hygiene` | 脏路径**全是** `.ccc/`（及 harness 噪音，见 B2） | **否**（ready 可 true；勿报「业务脏」） |
| `business` / `mixed` | 有 scope 外业务文件（`src/` `config/` 非噪音 `docs/` 等） | **是**（需人 override 或先收口） |

**Agent 对老板**：脏 200 个文件若几乎全是 `.ccc/board|events|pids` → 说「编排产物未扫，不挡开发」；**禁止**恐吓成「仓库烂了下不了任务」。

### A4. dirty_block 怎么处理（不是改意图）

1. 读 note：`business dirty outside plan scope` + 路径列表  
2. 若全是 B2 噪音 → 认平台噪音门禁；**同卡 reopen / 结算**，勿当业务失败改大卡  
3. 若有真业务脏且不在 scope → 人话说明挡路文件；可选：收窄下次 scope、或人 override；**禁止**默认投卫生 epic  
4. 验证-only（scope 已在盘上、无代码可改）→ 允许 DoD stamp（`.ccc/reports/<tid>.verify-stamp.md`）过门，勿逼 OpenCode 假改文件

### A5. 多 agent / 同仓并行

- 同仓 OpenCode **1 路**；跨仓 `MAX_CONCURRENT` 正交  
- **禁止**全量 add；提交前 `git status` 核对无他人改动混入  
- 需要隔离时用 worktree（平台开发）；业务产线默认串行同仓

---

## B. 文件夹卫生（硬）

### B1. 业务仓 `.ccc/` 该有什么（正常 ≠ 脏病）

| 路径 | 角色 | Agent 态度 |
|------|------|------------|
| `.ccc/board/{backlog…released,abnormal}/` | 看板 JSONL | 过程态；`ui_hidden`/done 沉底后勿当待办数 |
| `.ccc/plans` `phases` `reports` `verdicts` `pids` | 任务产物 | 随卡生命周期；quarantine 可留证据 |
| `.ccc/stats/failures.jsonl` | 失败账本 | **不删**（清板也不删） |
| `.ccc/quarantines/<tid>/` | 归档证据包 | 优化定稿时读；勿当「已删除」 |
| `.ccc/agent-mind/` | L1 项目脑 | 系统编译 + 提案；禁止 invent 当记忆 |
| `.ccc/lessons/` `.ccc/.product-fail-counter/` | 失败学习副作用 | **harness 噪音**（见 B2） |
| `docs/lessons.md` `docs/reports/*` | 教训/探针报告 | reports 探针多为噪音；lessons.md 追加勿挡 DoD |

### B2. Harness 噪音白名单（不得当 business dirty 结案）

以下路径**默认不挡** DoD / 不得写成「业务仓库脏了」：

- `docs/reports/`、`docs/lessons.md`、`docs/lessons/`  
- `.ccc/lessons/`、`.ccc/.product-fail-counter/`  
- 典型编排：`.ccc/board/` `.ccc/stats/` `.ccc/pids/` `.ccc/quarantines/` `.ccc/plans/` `.ccc/phases/` `.ccc/reports/` `.ccc/verdicts/`（除非本卡 scope **就是**改它们的 board_ops）

实现 SSOT：`_task_commit._is_harness_noise_path` + `_is_ccc_meta_path`。

### B3. 板面 / 文件夹「看起来乱」时 Agent 顺序

1. `hub_board` / `hub_git`：看 `dirty_kind`、`inflight`、`abnormal`（过滤 `ui_hidden` 与 epic `done`）  
2. **活跃板计数** ≠ backlog 文件个数  
3. 残卡 / 幽灵轨 → `abnormal-solve-sop` + `board-auto-repair-sop`（解决到可验收）  
4. **禁止**：教用户手删 `.ccc`；禁止默认 `executor_intent: python` 卫生 epic 当主业；禁止把 quarantines 当垃圾清空证据  

### B4. CCC 平台仓 vs 业务仓（文件夹边界）

| 仓 | Agent 可写？ |
|----|----------------|
| 本机 CCC（engineer） | 平台小改可以 |
| 2017 业务仓（qb 等） | **禁止**直写源码；只经定稿 transfer → Engine |
| 业务仓 `.ccc/` | 仅经 Hub 板务 / Engine；Agent 用 `hub_repair` 等，不 SSH 手搓 |

---

## C. 对老板怎么说（语感）

- ✅「编排产物有点多，不挡这张意图；卡在验收/挂死，我按解决 SOP 处理。」  
- ✅「commit 缺 task_id / 范围外脏文件，我先结算或改卡，不拿清目录当完成。」  
- ❌「仓库 200 个脏文件，先清卫生再说。」  
- ❌「我已经 clear_blockers 了」（若未结算/未优化定稿）

---

## D. 检查清单（Agent 每轮异常/脏树）

- [ ] 是否用了 dirty 三分法（而非文件个数）？  
- [ ] dirty_block 路径是否其实是 B2 噪音？  
- [ ] 是否已有含 `task_id` 的 commit + 验收绿 → 应结算而非重投？  
- [ ] 新定稿 scope 是否窄、acceptance 是否短命令、是否写「已绿即停」？  
- [ ] 有没有建议 `git add -A` 或卫生 epic 主业？→ 删掉  

## 冷却

文件夹「看起来乱」**不**单独升运维红；只有真业务脏挡下达、或异常解决 SOP 失败才升红。
