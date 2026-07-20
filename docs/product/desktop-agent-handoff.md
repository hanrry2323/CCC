# Desktop Agent 交接：业务仓迁移与接入

> **给 Desktop / Hub / Cursor Agent 的短交接**（日常心智）。  
> 五仓舰队迁移运维清单（仅执行迁移时打开）：[`../deploy/fleet-apps-migration-2026-07.md`](../deploy/fleet-apps-migration-2026-07.md)。  
> 单仓步骤 SSOT：[`../runbooks/app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md)。  
> 触发：「迁移到 2017」「接入 CCC」「桌面端怎么打开项目」「下一步做什么」。

---

## 你必须先懂的边界（现行真理）

```text
编排 SSOT = Mac2017 /Users/fan/program/apps/<name>（git main）
对话 cwd  = M1 ccc.localWorkspaceMap → /Users/apple/program/apps/<name>（瘦 clone）
M1 archive 冷冻树 = 只读备份，禁止 register / 禁止当开发 cwd
```

1. **编排 SSOT = Mac2017** `~/program/apps/<name>`（规范：进 `apps/`，勿顶层乱放）。  
2. **对话 = M1 Desktop + sidecar**；cwd 必须是 **M1 本机路径**（`ccc.localWorkspaceMap`）。  
3. **一项目一对话**：`{project_id}::main`；点项目卡即进入；「重置」≠ 新建 thread。  
4. **CCC orch 不可下达**；只对 `role=app` 且已 register 的仓转任务。  
5. **红线 12**：不擅自 `enable` 控制面。  
6. **主力开发在 2017**；M1 瘦副本仅对话 / 偶发本机改文件后须 push → 2017 pull。

---

## 生产路径（迁后）

| 角色 | 机器 | 路径 |
|------|------|------|
| orch | Mac2017 | `/Users/fan/program/CCC` |
| 业务 app | Mac2017 | `/Users/fan/program/apps/<name>` |
| 对话瘦 clone | M1 | `/Users/apple/program/apps/<name>` |
| 冷冻备份 | M1 | `/Users/apple/program/archive/2026-07-20-m1-freeze/<name>/` |
| CCC 客户端副本 | M1 | `/Users/apple/program/CCC`（改 CCC 用 Cursor，不下达） |

**生产 apps（2017）**：`ccc-demo`、`clawmed-ccc`、`xianyu`、`qb`、`qx-observer`、`hp`、`medio-0`。  
**Hub `project_id`**：通常 = 目录名；例外 **`qxo` → path `apps/qx-observer`**（map 键用 `qxo`）。`medio-0` 小写。

布局 SSOT：[`../deploy/server-layout.md`](../deploy/server-layout.md)。

---

## 迁移「完毕」后强制下一步（按序）

```text
落盘 apps/<name> → ccc-init → --register → doctor
→ 告知用户配置 M1 localWorkspaceMap（指向 ~/program/apps/<name>）
→ Desktop 刷新 → 点项目卡验证对话
→（用户要自动跑时）再提 enable —— 等用户点头
```

### Mac2017（SSH `fan@192.168.3.116`）

```bash
# 例：hp（五仓同形）
test -d /Users/fan/program/apps/hp/.git || echo "尚未落到规范路径"
python3 /Users/fan/program/CCC/scripts/ccc-init.py /Users/fan/program/apps/hp
python3 /Users/fan/program/CCC/scripts/ccc-init.py /Users/fan/program/apps/hp --register
python3 /Users/fan/program/CCC/scripts/ccc-workspace-doctor.py
python3 /Users/fan/program/CCC/scripts/ccc-sync-agent-roots.py
```

### M1 Desktop

1. 瘦 clone 存在：`/Users/apple/program/apps/<name>`（**不是** `archive/...-m1-freeze/`）。  
2. 设置 `localWorkspaceMap`：`"<project_id>" → /Users/apple/program/apps/<name>`。  
3. 侧栏出现项目卡 → 点击 → 中间栏即该项目对话框。  
4. 用户路径：对齐基线 → 定稿 → 转任务。

### 验收（你要能回报）

| 检查 | 期望 |
|------|------|
| 2017 `apps/<name>` | 存在且有 `.ccc/board` |
| `~/.ccc/workspaces.json`（2017） | 有该 app，`engine_eligible`/`engine` 合理 |
| `GET /api/desktop/projects` | 列表含该 `project_id` |
| Desktop 点卡 | 进入 `{id}::main`，sidecar 健康可聊 |
| 冷冻树 | 仅备份；**未**出现在 map / register |

---

## 对用户怎么说（口径）

- 「代码在 2017 编排；你在 Desktop 点项目卡聊；转任务后 Engine 在 2017 跑。」  
- 「一个项目只有一个对话；不要找第二个聊天窗口。」  
- 「没在侧栏出现 = 还没 init/board 或 Hub 未刷新；能聊不能下任务 = 还没 register。」  
- 「M1 冷冻目录是备份，不是工作区。」

---

## 禁止

- 只搬文件就宣布完成  
- 对 CCC 仓下业务 epic  
- 擅自 enable Engine  
- 发明多 thread / 「再开一个项目对话框」  
- 把业务仓塞进 `~/program/CCC` 或 `archive/` 当生产路径  
- 把 `archive/*-m1-freeze/` 配进 `localWorkspaceMap` 或 register  
- 声称 M1 旧顶层路径（如 `/Users/apple/program/xianyu`）仍是 Engine SSOT  

详步骤与反例 → [`app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md) · 五仓清单 → [`fleet-apps-migration-2026-07.md`](../deploy/fleet-apps-migration-2026-07.md)。
