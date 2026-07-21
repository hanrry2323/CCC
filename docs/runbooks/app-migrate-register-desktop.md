# 业务仓：迁移 → CCC 注册 → Desktop 对话

> **SSOT（单仓操作流程）**。对齐：[`../workspace-binding.md`](../workspace-binding.md)、[`../deploy/server-layout.md`](../deploy/server-layout.md)、[`../product/project-as-conversation.md`](../product/project-as-conversation.md)、[`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)。  
> **Agent 交接摘要**：[`../product/desktop-agent-handoff.md`](../product/desktop-agent-handoff.md)。  
> **五仓舰队迁移（运维清单，非日常心智）**：[`../deploy/fleet-apps-migration-2026-07.md`](../deploy/fleet-apps-migration-2026-07.md)。

---

## 0. 一句话

代码权威与 Engine 在 **Mac2017 `~/program/apps/<name>`**（CCC 已 register）；GitHub 为远端备份。  
人在 **M1 Desktop** 点项目卡进入 **唯一对话** `{project_id}::main`；对话事实只信 **Hub baseline**；转任务/看板走 **Hub → 2017 仓**。  
**M1 不保留业务源码第二树**（无 `~/program/apps/<业务>`、无旧顶层、无 freeze 当工作区）。

---

## 1. 双机分工（勿混）

| 面 | 机器 | 路径习惯 | 职责 |
|----|------|----------|------|
| 编排 / 代码权威 | Mac2017 | `/Users/fan/program/apps/<name>` | 代码生产 SSOT、Board、Engine、Hub 项目发现与 baseline |
| 远端备份 | GitHub | 各仓 `origin` | 给人 / Cursor 同步；不是 Engine cwd |
| 对话 | M1 | 无业务仓目录 | Desktop + sidecar `:7788`；对齐基线 = Hub API |
| 平台自研 | M1 | `/Users/apple/program/CCC` | Cursor 改 CCC；可选 `localWorkspaceMap["ccc"]` |

**禁止**：新业务仓落在 2017 顶层 `~/program/<name>`（规范要求进 **`apps/`**）。  
**禁止**：在 M1 为业务仓配 `localWorkspaceMap` 或保留 lean clone。

---

## 2. 标准流程（迁移完毕之后）

```text
① 代码落到 2017 apps/<name>
② ccc-init（+ --register）
③ doctor / sync-agent-roots
④ Desktop 刷新项目 → 点项目卡 → 进入 {id}::main 对话
⑤ 对齐基线（Hub）→ 定稿 → 转任务（Engine enable 后自动跑）
```

### ① 落盘（Mac2017）

```bash
# 规范路径（以 clawmed-ccc 为例）
mkdir -p /Users/fan/program/apps/clawmed-ccc
# git clone / 从 GitHub 拉 —— 保证 .git + 源码到此
```

验收：`test -d /Users/fan/program/apps/clawmed-ccc/.git`

### ② CCC 接入 + 注册（Mac2017）

```bash
python3 /Users/fan/program/CCC/scripts/ccc-init.py /Users/fan/program/apps/clawmed-ccc
python3 /Users/fan/program/CCC/scripts/ccc-init.py /Users/fan/program/apps/clawmed-ccc --register
# 或：python3 .../ccc-workspace-doctor.py register /Users/fan/program/apps/clawmed-ccc
```

`ccc-init` 会：七列看板、`profile.md` / `state.md`、种子 `CLAUDE.md` / `AGENTS.md`。  
`--register` → `~/.ccc/workspaces.json`（`role=app`，`engine_eligible`）。

编辑认知（必做）：

```bash
$EDITOR /Users/fan/program/apps/clawmed-ccc/CLAUDE.md
$EDITOR /Users/fan/program/apps/clawmed-ccc/.ccc/profile.md
```

### ③ 舰队卫生（Mac2017）

```bash
python3 /Users/fan/program/CCC/scripts/ccc-workspace-doctor.py          # ERROR=0
python3 /Users/fan/program/CCC/scripts/ccc-sync-agent-roots.py          # 白名单
cat ~/.ccc/workspaces.json | grep -A5 clawmed-ccc
```

控制面（需要自动跑队列时，**用户显式**）：

```bash
bash /Users/fan/program/CCC/scripts/ccc-autostart-guard.sh enable --start
```

红线 12：Agent **不得**擅自 enable。

### ④ M1 Desktop（无业务副本）

- **不要** `git clone` 业务仓到 M1。  
- **不要**写业务键进 `ccc.localWorkspaceMap`（仅平台 `ccc` 可选）。  
- 清空 / 删除历史：`~/program/apps/<业务>`、旧顶层、`archive/*-m1-freeze/`。

### ⑤ Desktop 打开项目对话框

产品契约：**一项目一对话**（见 `project-as-conversation.md`）。

| 用户动作 | 系统行为 |
|----------|----------|
| 侧栏点 **clawmed-ccc** 卡 | 切对话面；hydrate `clawmed-ccc::main` |
| 中间栏发消息 | sidecar cwd 默认平台仓或空策略；**业务事实来自 Hub 基线/会话**，勿当本机业务树 |
| 「重置对话」 | 清空本机会话 + drop sidecar slot（**不是**新建第二个 thread） |
| 「定稿 → 转任务」 | Hub 在 **2017** 仓写 epic；右栏绑 epic |
| Engine | 扫 **2017** `apps/clawmed-ccc/.ccc/board` |

**没有**「再开一个独立对话框」：换话题用重置，或换项目。

### ⑥ 人机主路径

```text
对齐基线 → 下一步 → 定稿方案 → 转任务 → 下达
→ Engine：product 扇出 → dev → review/test → kb → released
```

---

## 3. 注册 vs 发现（管理口径）

| 状态 | Hub 侧栏 | 可对话 | 可转任务 / Engine |
|------|----------|--------|-------------------|
| 仅有源码、无 `.ccc/board` | 不可见 | — | — |
| 有 board，未 register | 可见 | 是（Hub 基线） | **否**（`engine_eligible=false`） |
| `ccc-init --register` | 可见 | 是 | **是**（app） |
| `unregister` | 仍可能可见 | 是 | 否（暂停自动化） |
| CCC orch | 可见 | 运维可聊 | **禁止下达**（R-15） |

常用命令：

```bash
python3 .../ccc-workspace-doctor.py register <path>
python3 .../ccc-workspace-doctor.py unregister <path|name>
python3 .../ccc-workspace-doctor.py prune --apply
```

---

## 4. Agent 自检清单（迁移后「下一步」）

迁移文件完成后，**按序做**，不要停在「搬完了」：

1. [ ] 2017 路径是 `~/program/apps/<name>`（不是顶层乱放）  
2. [ ] `ccc-init` + `--register`；`workspaces.json` 有 app 条目  
3. [ ] `doctor` ERROR=0；必要时 `sync-agent-roots`  
4. [ ] Hub `GET /api/desktop/projects` 含该项目且 `engine_eligible` 符合预期  
5. [ ] M1 **无**该业务仓本机目录；`localWorkspaceMap` 无业务键  
6. [ ] Desktop 点项目卡能进对话；发一句「对齐基线」有回复（Hub 快照）  
7. [ ] （可选）定稿转任务后右栏出现 epic；Engine enable 后看板有动静  

卡在某步 → 查 [`workspace-binding.md`](../workspace-binding.md) §5–6，**不要**对 CCC orch 下业务 epic。

---

## 5. 反例（Desktop Agent 禁止）

- 声称「已迁移」但 2017 `apps/<name>` 不存在或无 `.git`  
- 只 rsync 代码、不做 `ccc-init` / register，就让用户去 Desktop 找项目  
- 把业务仓 init 进 CCC 编排仓，或对 CCC 下发 epic  
- 擅自 `autostart-guard enable`（红线 12）  
- 要求用户在 M1 再 clone 一份业务仓「才能聊」  
- 引导用本机 Read/git 核实业务仓（双权威）  
- 为同一项目创建多个 thread（违背 project-as-conversation）

---

## 6. 相关入口

| 文档 / 脚本 | 用途 |
|-------------|------|
| [`ccc-init.py`](../../scripts/ccc-init.py) | 一键接入 |
| [`ccc-workspace-doctor.py`](../../scripts/ccc-workspace-doctor.py) | 登记 / 卫生 |
| [`project-as-conversation.md`](../product/project-as-conversation.md) | 一项目一对话 |
| [`desktop-agent-handoff.md`](../product/desktop-agent-handoff.md) | Agent 短交接 |
| [`desktop-connection.md`](../product/desktop-connection.md) | Desktop↔Hub↔sidecar |
