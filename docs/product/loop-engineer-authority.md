# Loop Engineer — 事实权威与人机共识（SSOT）

> **状态**：现行 · 2026-07-22（Hub M1 主路径 = SSH 隧道 `:17777`；全流程完整性：假绿关门 / 活跃板计数 / VERSION opt-in） 
> **谁读**：老板 / Desktop Agent / Hub·sidecar / Cursor 改平台。  
> **冲突时以本文为准。** 边界流程：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> **规则**：你我共识 → **写入本文（或明确指向本文的一节）** → 再改代码/人格；禁止只留在聊天里。

---

## 一句话（开发路径）

**人定意图 → Hub 下达 → Engine 编排扇出 → 权威仓写码 → 验收纠错 → 回流飞轮；全程只认一个权威仓。**

（叙事：[`../VISION.md`](../VISION.md)。）

---

## 双 Agent 人格独立（硬 · 2026-07-22）

| | **Cursor（平台开发）** | **Desktop Agent（对话面）** |
|--|------------------------|------------------------------|
| 在哪 | Cursor IDE · 本仓 `/Users/apple/program/CCC` | M1 App · sidecar → loop-code |
| 职责 | **改 CCC 平台**：读/写/跑测/提交/排障，完整 IDE 能力 | **定意图**：对齐事实、定稿 epic、转任务；默认 Plan（硬禁写业务仓） |
| 人格 SSOT | 本仓 Cursor 规则 + [`dev-channel.md`](dev-channel.md) | [`desktop-agent-identity.md`](desktop-agent-identity.md) + `hub_voice.py` |
| 工具门禁 | **无** Desktop discuss allowlist；不受 Plan「不写码」约束 | discuss：除 Write/Edit 外全开；engineer 仅 `ccc` |

**禁止串台**：

1. **禁止**把 Desktop Plan 的「不写码 / 只产 epic / 透镜纪律」套到 Cursor 头上，当作 Cursor「能力限制」。  
2. **禁止** Cursor 会话自称 Desktop 对话搭档，或按 Desktop 人格前缀作答。  
3. **禁止** Desktop 人格文案写「你就是 Cursor」或反过来；功课可以深，**身份不可混**。  
4. Desktop 工具/人格改动 **只影响** sidecar→loop-code；**不**削弱 Cursor 改平台的能力。

平台开发通道：[`dev-channel.md`](dev-channel.md)。

---

## 闭环七词

| 词 | 含义 |
|----|------|
| **意图** | 人在 Desktop 聊透目标与验收 |
| **下达** | 定稿 transfer；进队后不逐步人批 |
| **编排** | Engine 扇出 work、调度阶段 |
| **写码** | 只在 2017 权威仓；plan 白名单 |
| **纠错** | verdict 落盘；abnormal 止损 |
| **飞轮** | 归档 / 回测 / 再定意图 |
| **权威** | 代码与看板只在 register 仓；透镜 live |

**已注册 ≠ 可正式开发。** 正式交给 CCC 前须**全面对齐**（baseline + live 透镜 + risks + 可下达边界）。

**平台开发工具：只认 Cursor，不更换**（[`dev-channel.md`](dev-channel.md)）。仓内若残留 Trae/Zed/「用 Claude Code 改平台」等现行指引 → 删除或标史。

---

## 行业共识（我们认可）

| 判断 | 结论 |
|------|------|
| Demo ≠ 上线 ≠ 稳定符合意图 | **行业共性**，非个人特例 |
| AI 擅 happy path；缺边界/验收/纠偏环 | 高级/低级模型都快到「能跑」，后半段才是鸿沟 |
| 接手老仓难于从零 | 隐性规则在人脑；须先对齐再交给 agent |
| 路线曲折、模型误解 | **默认**；产品要做闭环，不幻想一次聊完 |

CCC 卖的不是「更快写出第一版」，而是把后半段**工程化**。

---

## 价值立场（2026-07-21 评估）

| 项 | 口径 |
|----|------|
| 加权约 **7.2/10** | **值得继续做**，只压「闭环工程」 |
| 值钱 | 意图门 · 对话/编排分离 · 权威仓+透镜 · verdict/旁路收死 |
| 不值钱 | 复刻 IDE · 堆角色 · 堆文档 · 「接很多模型/多 IDE」当卖点 |
| 平台开发 | **只认 Cursor**；不换工具 |
| 下一程证明 | 已对齐业务仓连续 **3 次**「定稿→在飞→verdict」可复述可纠；达不到就收范围 |

评分画布（讨论产物）：Cursor canvases `ccc-value-scorecard` / `ccc-pain-loop-stages`。

---

## 三阶段（都能接，门禁不同）

| 阶段 | 适配 | 交给 CCC 前须齐 |
|------|------|-----------------|
| 从零新建 | 强 | 意图 + 验收标准 |
| 接手老项目 | 中→强 | **全面对齐硬门** |
| 日常维护 | 强 | 小目标 + 白名单 + verdict |

**已注册 ≠ 可正式开发。** 正式交给 CCC 前须**全面对齐**：baseline + live 透镜 + risks + 可下达边界。

**平台开发工具：只认 Cursor，不更换**（[`dev-channel.md`](dev-channel.md)）。仓内若残留 Trae/Zed/「用 Claude Code 改平台」等现行指引 → 删除或标史。

### Desktop 流畅原则（人机共识）

**人只定意图；投递/连通/重试/进 Hub/进队列 = 系统后台，用户不碰。**  
**确认不依赖 Hub 可达**；Hub 灯只表示投递/编排同步健康，不挡确认。  
**唯一冲刷器 = sidecar**（Desktop 只 `enqueue` + 可选 nudge；关 App 不停）。

| 前台（人确认） | 后台（系统扛） |
|----------------|----------------|
| 定稿 / 点转任务 / 切看板 | Hub 连通、投递、重试、卡死恢复 |
| 立刻关 sheet、徽章 `queued`、可继续聊 | 入本机 outbox；**sidecar 常驻 flush** → Hub；成功写 `transfer-receipts.json` |
| 看板始终画列（可空） | 拉板失败保留快照 + 短超时，不整页死白 |

**Agent 定方案（硬）**：讨论 / 下一步 / 定稿时，按用户意图制定**最佳方案**并默认推进；**禁止**每轮甩拍板选择题、**禁止定稿后再问要不要入队**。仅当真缺不可逆信息才最多 1 问。定稿白话给用户可读结论；`ccc-transfer` 契约折叠给 Engine，不把任务 id/路径清单当结论。看板/产物卫生：`executor_intent=python`（Hub 对 ops/卫生意图会把 opencode 强制归一为 python）；**不存在 committer 绕过 Engine**；`pipeline=ops` 仍扇出。abnormal 未核账禁止重复下达同目标卡。

禁止：
- 让用户管「是否进 Hub / 是否还在队列 / 要不要重开 App 冲刷」
- 用全局 `busy` 把对话/切页锁死在一次 Hub 往返上
- Desktop 与 sidecar **双 POST** Hub transfer（只认 sidecar 单写）

关 Desktop ≠ 停编排：Hub/Engine 在 2017 继续；本机 outbox 由 `com.ccc.agent-sidecar` 冲刷到 Hub。

### 关再开接续（R1–R12）

| # | 行为 | 结论 |
|---|------|------|
| R1 | 投递徽章 | hydrate 优先 `transfer-receipts.json`，再 outbox / failed / 磁盘 flow |
| R2 | 看板首屏 | `board-cache-<project>.json` 冷启动；失败保留 + stale |
| R3 | 回前台 | `scenePhase.active` → flush + bindFlow + summaries（用户无动作） |
| R4 | fanout 提示 | 未拆分 epic 再开后重挂 15s watchdog |
| R5 | 空态 | 有 `boundEpicId` 显示「编排同步中…」，禁闪「编排空闲」 |
| R6 | 侧栏灯 | bootstrap 立即 `fetchBoardSummaries`，不等首轮 poll |
| R7 | Chat 页 | 仅 summaries ~20s 刷灯；整板只在 Board 页轮询 |
| R8 | 单 flush | Desktop 只 nudge sidecar；按 receipts/outbox 校正徽章 |
| R9 | 投递耗尽 | 持久 failed 条 + 「后台再试」；**Hub 恢复时自动 requeue**（非只靠用户点） |
| R10 | SSE cursor | 不改协议；靠 snapshot 接续；中间动画可缺 |
| R11 | 聊天半句 | **不做**中途 SSE 重挂；再发可 resume |
| R12 | 全局 busy | Hub 往返（含手动建 epic）不锁 `busy` |

再开 = 磁盘 hydrate + 后台 catch-up；**用户无需点同步**。

### Hub 传输（M1 · 硬 · 2026-07-22）

| 项 | 口径 |
|----|------|
| **权威 Hub 仍在 2017** | 进程听 `*:7777`；契约 / transfer / mind / lens **不变** |
| **M1 主路径** | SSH 本地转发 `127.0.0.1:17777` → 2017 `127.0.0.1:7777`（launchd `com.ccc.hub-tunnel`） |
| **Desktop / sidecar 默认** | `http://127.0.0.1:17777`；**禁止**把 LAN `192.168.3.116:7777` 写成 M1 默认 |
| **为何** | LAN 直连 `:7777` 曾 TCP 通但 HTTP 整段超时（Send-Q 积压）；隧道探活满绿 |
| **文档** | [`hub-ssh-tunnel.md`](hub-ssh-tunnel.md) · [`desktop-connection.md`](desktop-connection.md) |

安装：`bash scripts/install-hub-tunnel-plist.sh --start`。心智 / 透镜 / outbox 一律走同一 `CCC_HUB_URL`。

### Desktop Agent 双层心智（人机共识）

| 层 | 内容 | 谁维护 | 落点 |
|----|------|--------|------|
| **L0 不变核** | 身份、红线、转任务闭环、透镜纪律 | **仅 Cursor / 平台仓**（`hub_voice` + 本文） | 每轮强制注入；Agent **禁止写** |
| **L1a 观察脑** | 看板计数、在飞、日报/周报要点、git 脏仓 | **系统编译** | 2017 `apps/<id>/.ccc/agent-mind/observed.json` |
| **L1b 决策脑** | 目标/约束/开放问题/架构取舍 | **Agent 提案 + Hub 校验** | 同目录 `decided.json` |

- API：`GET/PUT /api/desktop/mind/{project_id}/…`；sidecar **每轮**注入 digest（≤2KB），与 live board **并行拉取**，本机短缓存（约 20s）降隧道往返。
- 新鲜度：`live board / lens git` > L1 digest > 聊天 resume。
- 不复活 invent；心智沉淀 ≠ 自动投 backlog。
- Hub 断 / 隧道断：明说 L1 不可达，**禁止**用聊天 resume 编造在飞；转任务仍可 outbox。

### 活跃板计数与 ready（硬 · 2026-07-22）

| 信号 | 含义 |
|------|------|
| **活跃板计数** | lens / mind / baseline 与 Board API **同口径**：跳过 `ui_hidden=true` 与 epic `split_status=done`；`failed` 仍算活跃风险 |
| **pipeline_idle** | 过滤后 planned/in_progress/testing/abnormal=0，且无在飞 inflight |
| **git_clean** | 工作区 porcelain 空 |
| **ready_for_task** | `git_clean` **且** 无活跃 inflight（≠「仅 git 净」；≠「磁盘 backlog 文件数为 0」） |

禁止把 raw `backlog/*.jsonl` 文件数（含已 done+hidden 僵尸）当成「待办队列」推荐挑卡。

### 验收关门与 VERSION（硬 · 2026-07-22）

- **跑完 ≠ 做对**：salvage / 进 testing 前必须过 hollow + acceptance（计划 `## 验收` 可重放命令或交付路径落在 task commit）；`ALL SELF-CHECKS PASSED` 字符串**不足以**单独放行。
- **complexity=small** 仅表规模提示，**不** stub 跳过 reviewer/tester。默认 **medium**。多步回归/三件套（acceptance 可执行条 ≥3 或模块标记 ≥3）禁止 small——Hub `resolve_complexity` 会抬升；扇出对真回归不因 small 强制单卡。
- **运行时冒烟验收**：`.venv/bin/python` / `python3` + 显式 `DRY_RUN=true`；禁止裸 `python`。
- **VERSION**：kb 默认 **不** bump；仅 transfer/epic 显式 `bump_version=true`（或 tag `bump-version`）才升版+changelog+tag。
- **看板卫生**：scope 在 `.ccc/board/**`（及 plans/phases/reports/verdicts/lessons/stats）且 executor∈{python,auto,cli} → 确定性 board_ops 短路径，不进 opencode 长跑。Hub 对 ops/卫生意图强制 `python`。
- **止损清场**（Agent/平台排障）：failed epic + abnormal work 归档出板后，还必须清 `last_epic` / `epic_history` 与 `~/.ccc/flow-events.jsonl` 中该 epic，否则右栏 `bound_hint` 幽灵复活。

---

## 四权威（只认这张表）

| 权威 | 落点 | 谁可写 |
|------|------|--------|
| 意图 / 会话 | M1 Desktop `sessions/` | 人 + 讨论 Agent（聊） |
| 编排看板 | 2017 `apps/<id>/.ccc/board` | Hub transfer + Engine |
| **代码 SSOT** | 2017 已 register 的 `apps/<name>` | **仅** Engine 阶段执行器 |
| 远端备份 | GitHub | 人 / Cursor 同步；**不是**对话或 Engine cwd |

M1：**无**业务源码第二树；`localWorkspaceMap` 仅可选 `ccc` → 本机 CCC。

---

## 讨论 Agent 事实源

| 来源 | 用途 |
|------|------|
| Hub baseline | 开场（点时快照 + live board） |
| Hub **只读透镜** `/api/desktop/lens/{id}/…` | live 看板 / locate / 文件 / grep / git |
| Hub **项目心智** `/api/desktop/mind/{id}/digest` | L1 观察脑+决策脑短摘要（每轮） |
| 本机会话 | 已聊目标与约束（低于 digest/board） |
| 本机 Read/git | **仅** `ccc` |

CLI：`python3 scripts/ccc-hub-lens.py board|locate|tree|file|grep|git <project_id> …`  
心智写入：`python3 scripts/ccc-mind-update.py <project_id> --constraint '…'`  
禁止 sidecar `ssh mac2017` 探业务仓。问看板/文件 → **先透镜**；Hub 断 → 明说，禁止瞎编。

**扫风险 / 定稿**：必须定点核实真代码（`locate`/`grep` → `file`），禁止只读文档交差；禁止全仓无脑扫。路径只认 `project_id` + 透镜相对路径。

---

## 工程师模式

| 项目 | 规则 |
|------|------|
| 业务仓 | **拒绝** engineer |
| 平台仓 `ccc` | 可本机改 CCC |

业务改码：**定稿 → transfer → Engine**。

---

## 讨论 = Plan（规划面 · **仅 Desktop**）

> **适用范围**：只约束 **Desktop sidecar → loop-code**。  
> **不约束 Cursor**。Cursor 改本仓 = 完整 IDE 能力（见上文「双 Agent 人格独立」）。

| 维度 | 规则 |
|------|------|
| 协议 | Desktop 仍传 `tool_mode=discuss`（少动协议）；`prompt_mode` 恒 full（已取消 light） |
| 智力 | 全开：Read/Glob/Grep/Bash/Web*/Task·Agent + Hub 透镜（含 locate） |
| 执行 | **硬禁** Write/Edit/MultiEdit/NotebookEdit；子代理同样禁写 |
| 交付 | 定稿 / `plan_md` / 转任务契约，**不是**仓库 diff |
| 业务仓 | 事实只认 Hub 基线 + 透镜；禁止假装本机有第二树；禁止写死 2017 盘符 |

工程师模式 = **仅 Desktop 会话**里对 `ccc` 可写；业务仓口令无效。Desktop 代码定位 = 透镜 `locate`（业务仓不走 Cursor MCP）。

---

## 扇出角色（讨论面须知 · 勿扮演）

| 角色 | 可写 | 硬规则 |
|------|------|--------|
| product | plan/phases/扇出；不写源码 | cwd=2017 apps |
| dev | 仅 plan 白名单 | 红线 3 |
| reviewer/tester | verdict/report | Verdict 落盘才算 |
| 讨论 Agent（Plan） | 无业务写 | 透镜只读 + `ccc-transfer`；可子代理调研 |

---

## 共识如何落盘（强制应用）

以后你我达成共识，执行顺序：

1. **改本文**（或在本文增加一节并改「状态」日期）——权威。  
2. **改入口**：`STARTUP-BRIEF.md` / `CLAUDE.md` / `.cursor/rules/loop-engineer-consensus.mdc` / 必要时 `hub_voice.py`——应用。  
3. **不要**另起平行「现行真理」长文；史实类标「史」并指回本文。  
4. 讨论画布可留作评分/梳理附件，**不**替代本文。  
5. **可巡查硬卡**同步：`references/authority-patrol.jsonl`（给机器探针用，不是给人读的说明书）。

---

## 平台自动维护 + 违背才找老板（硬 · 2026-07-22）

目标是 vibe 自动化：日常维护 **不问你**；只有 **违背本文硬共识** 才用人话喊你拍板。

| 区 | 谁做 | 要不要你点头 |
|----|------|--------------|
| **绿灯（自动）** | Cursor 平台维护：对齐版本、清过时改法指引、修测试红、双机同步热更、止损清场、回填 hub_voice/L1 | **不要** |
| **红灯（决策）** | 权威巡查发现违背本文（或明确指向本文的硬卡） | **要**——桌面通知 + `~/.ccc/alerts/` 人话文件 |

硬口径：

1. **平台养仓只认 Cursor**（定时 Automation / 会话 / hook）；**禁止** Engine invent 养 CCC orch。  
2. **默认可自动**：未踩红线就直接干，禁止反复「这样行吗」。  
3. **唯一打断你**：巡查脚本 `scripts/ccc-authority-patrol.py` 发现违规 → `ccc-notify` L3（人话：发现了什么 / 为何算违背 / 建议怎么选）。  
4. **你不读长文档**：报警正文即决策界面；拍板后改本文或改实现，下次巡查变绿。  
5. **经验进配置**：authority + Cursor rule + hub_voice + 巡查卡；**禁止**另堆给你看的平行 brief。

---

## 从零测 ccc-demo

1. 对齐基线 → 空板 + live `as_of`。  
2. 定稿转任务 →「刷新看板」见在飞 work。  
3. Hub 断 → 明说不可达。  
4. 业务仓工程师模式 → 拒。

板面重置归档：`apps/ccc-demo/.ccc/archive/reset-2026-07-21/`。

---

## 文档怎么读

| 优先级 | 文档 | 管什么 |
|--------|------|--------|
| **1** | **本文** | 路径 / 权威 / 共识 / 价值立场 |
| 2 | [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) | 过桥 |
| 3 | [`desktop-agent-handoff.md`](desktop-agent-handoff.md) | 接入 |
| 4 | [`desktop-agent-identity.md`](desktop-agent-identity.md) | 口吻 |
| 史 | [`m1-no-second-tree-closeout.md`](m1-no-second-tree-closeout.md) | 清扫记录 |

总索引：[`../INDEX.md`](../INDEX.md)。

---

## 禁止

- M1 业务第二树当权威  
- 讨论 Agent SSH 写 2017 / 扮演 product·dev  
- 过期 baseline 否定 live 看板  
- 业务仓工程师旁路  
- 共识只留在聊天、不落本文  
- **把 Desktop Plan 门禁当成 Cursor 能力上限**；**Cursor / Desktop 人格串台** 

## API

`GET /api/desktop/lens/{id}/board|tree|file|grep|git/summary`
