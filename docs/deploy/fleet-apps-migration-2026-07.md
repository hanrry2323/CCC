# 舰队业务仓迁移：M1 → Mac2017 apps/（2026-07）

> **运维迁移 SSOT**（人 / 迁移执行时打开）。  
> **不是**日常开发默认真相 —— Agent 日常心智见 [`../product/desktop-agent-handoff.md`](../product/desktop-agent-handoff.md) + [`server-layout.md`](server-layout.md)。  
> 单仓通用步骤：[`../runbooks/app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md)。

---

## 0. 目标与不做

**一次迁入五仓**到 Mac2017 `~/program/apps/<name>`，以 **GitHub `main` 干净 clone** 为准；M1 旧树 **冷冻备份**；2017 **新建空 `.ccc`**（不迁旧看板垃圾）。

| Hub / 目录名 | M1 迁前路径 | GitHub | 2017 目标 |
|--------------|-------------|--------|-----------|
| `xianyu` | `/Users/apple/program/xianyu` | `hanrry2323/xianyu` | `/Users/fan/program/apps/xianyu` |
| `qb` | `/Users/apple/program/projects/qb` | `hanrry2323/qb` | `/Users/fan/program/apps/qb` |
| `qx-observer`（昵称 qxo） | `/Users/apple/program/qx-observer` | `hanrry2323/qx-observer` | `/Users/fan/program/apps/qx-observer` |
| `hp` | `/Users/apple/program/hp` | `hanrry2323/hp` | `/Users/fan/program/apps/hp` |
| `medio-0` | `/Users/apple/program/Medio-0` | `hanrry2323/medio-0` | `/Users/fan/program/apps/medio-0` |

**已在 2017、不重复迁**：`ccc-demo`、`clawmed-ccc`（测试中）。orch：`/Users/fan/program/CCC`。  
**不进 Engine**：`ai-loop-router` → `infra/`；`qx` / `clawmed-ai` → 零件库。

**不做**：核心产品代码改动、前端页面、擅自 `enable` Engine（红线 12）、整仓 rsync、长期迁移分支。

---

## 1. 原则

1. **先整合 `origin/main`，再 2017 `git clone`** — 不以 rsync 整树为准。  
2. **垃圾隔离** — 不带 venv、`target/`、`node_modules`、`*.rdb`、旧 `.ccc` 任务垃圾、worktree。  
3. **2017 新建空看板**（`ccc-init`）— 旧 plans/phases/board 留在 M1 冷冻。  
4. **只保留 `main`** — 不建迁移分支；未推送提交整理进 `origin/main` 后推送。  
5. **主力开发在 2017** — Engine / 推送以 2017 工作树为准。

心智（迁后现行真理，与 handoff 一致；**2026-07-21 起 M1 不再留业务第二树**）：

```text
代码权威 = Mac2017 /Users/fan/program/apps/<name>（main，已 register）
远端备份 = GitHub
M1 对话  = Desktop；事实只信 Hub baseline；无业务 clone / 无 freeze 工作区
```
---

## 2. 单仓标准流水线

推荐顺序（风险升序）：**hp → xianyu → qb → qx-observer → medio-0**。

```text
① M1：整理 → push origin main
② M1：整树移入 archive/…-m1-freeze/<name>/（过渡；清扫后删除）
③ 2017：git clone → apps/<name>
④ 2017：ccc-init + --register → doctor → sync-agent-roots
⑤ M1：不保留业务 clone；Desktop 点卡对话（事实信 Hub baseline）
⑥ 冒烟：Hub 列表 / Desktop 点卡 /（用户同意后）最小转任务
```

### ① 整理 → `origin/main`

```bash
cd <m1_old_path>
git checkout main
git fetch origin
git status
git rev-parse HEAD origin/main   # 应对齐；有 ahead 则先处理再 push
# 有价值未提交：commit 后
git push origin main
# 验收
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

脏 `.ccc` / 本地产物：**不要**为推送强行把巨型二进制进 Git；untracked 运行时垃圾随冷冻树保留即可。

### ② M1 冷冻

```bash
STAMP=2026-07-20-m1-freeze
mkdir -p "/Users/apple/program/archive/${STAMP}"
# 例：hp
mv /Users/apple/program/hp "/Users/apple/program/archive/${STAMP}/hp"
```

冷冻根 `README.md` 模板：

```markdown
# M1 冷冻备份 — <name>

- **状态**：只读冷冻（迁移日备份）
- **生产 SSOT**：Mac2017 `/Users/fan/program/apps/<name>`
- **禁止**：Engine register、当作日常开发 cwd、把本树路径写进 localWorkspaceMap
- **对话瘦副本**：`/Users/apple/program/apps/<name>`（另 clone）
```

### ③ 2017 干净 clone

```bash
ssh fan@192.168.3.116
cd /Users/fan/program/apps
git clone git@github.com:hanrry2323/<repo>.git <apps_name>
# qx-observer → apps/qx-observer；medio-0 → apps/medio-0（小写）
```

**禁止**从 M1 rsync 整仓。密钥 / 本机 `.env`：人工按 `.env.example` 填，不进 Git。

### ④ CCC 注册

```bash
python3 /Users/fan/program/CCC/scripts/ccc-init.py /Users/fan/program/apps/<name>
python3 /Users/fan/program/CCC/scripts/ccc-init.py /Users/fan/program/apps/<name> --register
python3 /Users/fan/program/CCC/scripts/ccc-workspace-doctor.py
python3 /Users/fan/program/CCC/scripts/ccc-sync-agent-roots.py
```

- 登记名 / 目录 = `qx-observer`；**Hub / Desktop `project_id` = `qxo`**（Board 对 `qx-observer` 路径有硬编码别名，见 `ccc-board-server.py` discover）。  
- 昵称与 id 一致用 `qxo`；勿在 map 里只写 `qx-observer` 而漏 `qxo`。  
- `medio-0` 小写与 GitHub / 目录一致。

### ⑤ M1 对话（2026-07-21 起：无业务第二树）

**不要**再 `git clone` 业务仓到 M1，**不要**写业务键进 `ccc.localWorkspaceMap`。  
对话点卡即可；对齐基线走 Hub `/api/projects/{id}/baseline`。  
可选：仅平台 `ccc` → `/Users/apple/program/CCC`。

> 历史步骤（已废）：M1 `apps/<name>` 瘦 clone + map。勿再执行。

### ⑥ 冒烟验收（每仓勾选）

| 检查 | 期望 | hp | xianyu | qb | qx-observer | medio-0 |
|------|------|----|--------|----|-------------|--------|
| 2017 `apps/<name>/.git` + `.ccc/board` | 有 | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2017 `workspaces.json` 含 app | `engine` 合理 | ☐ | ☐ | ☐ | ☐ | ☐ |
| `doctor` ERROR=0 | 通过 | ☐ | ☐ | ☐ | ☐ | ☐ |
| `GET /api/desktop/projects` | 含 id | ☐ | ☐ | ☐ | ☐ | ☐ |
| Desktop 点卡 → `{id}::main` | 可聊 | ☐ | ☐ | ☐ | ☐ | ☐ |
| （可选）最小转任务 | 2017 board 有 epic | ☐ | ☐ | ☐ | ☐ | ☐ |

红线 12：Agent **不得**擅自 `autostart-guard enable`。

---

## 3. 垃圾排除 / 每仓附录

### 通用勿迁

`.venv` / `venv` / `node_modules` / `target/` / `__pycache__` / `.DS_Store` /  
`.ccc/plans|phases|reports|verdicts` 历史 / `engine-heartbeat.json` / pids /  
worktree / `_archive` 里的旧任务垃圾 / `*.rdb` / 大 `logs/` / `.env`（密钥）

### hp

- 最干净；第一枪。  
- 审视 `local/`：若未进 Git 则 2017 不自动拥有；按需白名单或文档说明。

### xianyu

- 迁前常 **ahead** — 先 push `main`。  
- 排除双 venv、`output`、coverage；大媒体按需。

### qb

- 迁前常 **ahead**。  
- **禁止**带 `dump.rdb` / `temp-*.rdb`、`logs/`、旧 `on-hold` 列。  
- M1 路径在 `projects/qb`；2017 / 瘦副本统一 `apps/qb`。

### qx-observer

- **路径 / 登记名** = `apps/qx-observer`；**Hub 发现 `project_id` 现为 `qxo`**（历史昵称）。  
- M1 **不**再为 `qxo` 配本机 map。  
- `templates`：勿链 M1 绝对路径；2017 链本机 `…/program/CCC/templates`。  
- 排除外部 worktree（`.qx-worker-*` 等）。

### medio-0

- 迁前常 **ahead**。  
- **禁止** rsync `target/`（约 11G）；只 `git clone` 源码。  
- 目录名 / id = **`medio-0`**（对齐 GitHub；勿用 `Medio-0` 作 2017 路径）。

---

## 4. 迁后路径总表（现行 · 2026-07-21）

```text
Mac2017（代码权威）
  /Users/fan/program/CCC
  /Users/fan/program/infra/ai-loop-router
  /Users/fan/program/apps/
    ccc-demo/  clawmed-ccc/
    xianyu/  qb/  qx-observer/  hp/  medio-0/
  /Users/fan/program/archive/

M1（对话壳 · 无业务第二树）
  /Users/apple/program/CCC                         # 改 CCC 用 Cursor；可选 map ccc
  /Users/apple/program/apps/                       # 空；禁止业务 clone
  （已删）archive/2026-07-20-m1-freeze/            # 2026-07-21 清扫
```

目标登记（2017 `~/.ccc/workspaces.json`）：orch CCC + 7 apps（demo + clawmed + 五仓）。

---

## 5. 执行记录（2026-07-20）

| 仓 | push main | 冷冻 | 2017 clone | init/register | 冒烟 | 备注 |
|----|-----------|------|------------|---------------|------|------|
| hp | ✅（已同步） | ✅（后删） | ✅ | ✅ | ✅ Hub 列表 | |
| xianyu | ✅（ahead 8→push） | ✅（后删） | ✅ | ✅ | ✅ Hub 列表 | 2017 清空旧 board 卡；历史进 `_pre_migration_artifacts` |
| qb | ✅（ahead 2→push） | ✅（后删） | ✅ | ✅ | ✅ Hub 列表 | 同上；M1 原路径 `projects/qb` |
| qx-observer | ✅（已同步） | ✅（后删） | ✅ | ✅ | ✅ Hub 列表 | Hub `project_id`=**`qxo`**，路径=`apps/qx-observer` |
| medio-0 | ✅（ahead 9→push） | ✅（后删） | ✅ | ✅ | ✅ Hub 列表 | 无 `target/`（~21M）；id=`medio-0` |

冷冻根（2026-07-20）：`…/archive/2026-07-20-m1-freeze/` → **2026-07-21 已从 M1 删除**（连同业务 lean clone / 相关 LaunchAgents）。  
2017 doctor（迁后）：`errors=0`；registered=8（orch+7 apps）。

### M1 LaunchAgents（2026-07-21 清扫）

指向 freeze / `apps/hp` 的 `com.qb.*` / `com.hp*` / `com.hp-kb.*` / `com.mavis.hp-kb-tunnel` 已 **bootout** 并移入 `~/.ccc/retired/launchagents-2026-07-21/`。  
`com.medio.deploy` 仍在 `~/Library/LaunchAgents/disabled-m1-migrate-20260720/`（若存在）。  
M1 不再保留业务源码第二树；对话事实只信 Hub baseline。

---

## 6. 相关入口

| 文档 | 用途 |
|------|------|
| [`desktop-agent-handoff.md`](../product/desktop-agent-handoff.md) | Agent 日常心智（勿把本文当默认上下文） |
| [`app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md) | 单仓操作 |
| [`server-layout.md`](server-layout.md) | 2017 `~/program` 布局 |
| [`dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md) | 对话面 / 编排面 |
| [`migration-m1-to-2017.md`](migration-m1-to-2017.md) | 基础设施切中转/Hub（已完成） |
