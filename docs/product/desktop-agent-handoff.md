# Desktop Agent 交接：业务仓迁移与接入

> **给 Desktop / Hub / Cursor Agent 的短交接**（日常心智）。  
> 五仓舰队迁移运维清单（仅执行迁移时打开）：[`../deploy/fleet-apps-migration-2026-07.md`](../deploy/fleet-apps-migration-2026-07.md)。  
> 单仓步骤 SSOT：[`../runbooks/app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md)。  
> 触发：「迁移到 2017」「接入 CCC」「桌面端怎么打开项目」「下一步做什么」。

---

## 你必须先懂的边界（现行真理）

> **完整契约**：[`loop-engineer-authority.md`](loop-engineer-authority.md)（冲突以它为准）。

```text
代码权威 = Mac2017 apps/<name>（已 register）
看板权威 = 同上 .ccc/board（Hub 透镜 live）
远端备份 = GitHub（不是对话 cwd）
M1        = 无业务第二树；baseline 开场 + 透镜 live
平台仓    = 本机 CCC（仅 ccc 可工程师模式）
```

1. 编排 SSOT = 2017 `apps/<name>`。  
2. 对话 = Desktop + sidecar；业务事实走 Hub，不走本机业务 clone。  
3. 一项目一对话 `{id}::main`。  
4. 不对 CCC orch 下达业务 epic。  
5. 红线 12：不擅自 enable。  
6. 写码只在 2017 Engine；业务仓拒绝工程师模式。

---

## 生产路径（迁后）

| 角色 | 机器 | 路径 |
|------|------|------|
| orch | Mac2017 | `/Users/fan/program/CCC` |
| 业务 app（权威） | Mac2017 | `/Users/fan/program/apps/<name>` |
| 远端备份 | GitHub | 各仓 `origin` |
| CCC 平台副本 | M1 | `/Users/apple/program/CCC`（改 CCC 用 Cursor，不下达） |
| 业务仓副本 | M1 | **不保留**（禁止 `~/program/apps/<业务>`、禁止旧顶层、禁止 archive 当工作区） |

**生产 apps（2017）**：`ccc-demo`、`clawmed-ccc`、`xianyu`、`qb`、`qx-observer`、`hp`、`medio-0`。  
**身份对照（勿混）**：

| Hub `project_id` | 2017 路径 | M1 对话事实源 |
|------------------|-----------|----------------|
| `ccc` | `…/CCC` | 平台仓可映射 `localWorkspaceMap["ccc"]`→本机 CCC；不对 orch 下达 |
| `ccc-demo` 等业务 | `…/apps/<名>` | **仅** Hub baseline / transfer；无本机业务 cwd |
| **`qxo`** | `…/apps/qx-observer` | 同上（id 别名，勿与路径名混） |

布局 SSOT：[`../deploy/server-layout.md`](../deploy/server-layout.md)。

---

## 迁移「完毕」后强制下一步（按序）

```text
落盘 2017 apps/<name> → ccc-init → --register → doctor
→ Desktop 刷新 → 点项目卡验证对话（对齐基线走 Hub）
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

1. **不要**再 clone 业务仓到本机；**不要**把业务路径写入 `localWorkspaceMap`。  
2. 可选：仅 `ccc` → `/Users/apple/program/CCC`（平台自研对话）。  
3. 侧栏出现项目卡 → 点击 → 中间栏即该项目对话框。  
4. 用户路径：对齐基线（Hub）→ 定稿 → 转任务。

### 验收（你要能回报）

| 检查 | 期望 |
|------|------|
| 2017 `apps/<name>` | 存在且有 `.ccc/board` |
| `~/.ccc/workspaces.json`（2017） | 有该 app，`engine_eligible`/`engine` 合理 |
| `GET /api/desktop/projects` | 列表含该 `project_id` |
| Desktop 点卡 | 进入 `{id}::main`，sidecar 健康可聊 |
| `GET /api/projects/{id}/baseline` | 有摘要；对齐基线不依赖本机业务树 |
| M1 业务目录 | **不存在** `~/program/apps/<业务>` / 旧顶层 / freeze 工作区 |

---

## 对用户怎么说（口径）

- 「代码权威在 2017；你在 Desktop 点项目卡聊；转任务后 Engine 在 2017 **自动**跑。」  
- 「一个项目只有一个对话；不要找第二个聊天窗口。」  
- 「没在侧栏出现 = 还没 init/board 或 Hub 未刷新；能聊不能下任务 = 还没 register。」  
- 「M1 不留业务源码副本；GitHub 是备份，不是第二权威。」  
- 「人只在定稿/采纳时拍板；进队后不加逐步批准。」  
- 被问「你是谁」：**禁止**提 flash 中转站 / `:4000`；口径见 [`desktop-agent-identity.md`](desktop-agent-identity.md)。

对话 Agent 身份/心智 SSOT：[`desktop-agent-identity.md`](desktop-agent-identity.md)。  
配置家：`~/.ccc/loop-code`（见 [`loop-code-ownership-cut.md`](loop-code-ownership-cut.md)）；**不要**读个人 `~/.claude`。

---

## 禁止

- 只搬文件就宣布完成  
- 对 CCC 仓下业务 epic  
- 擅自 enable Engine  
- 发明多 thread / 「再开一个项目对话框」  
- 把业务仓塞进 `~/program/CCC` 或本机 `apps/` / `archive/` 当对话权威  
- 在 M1 保留业务源码第二树或把旧顶层路径当 Engine SSOT  
- 引导 Agent 用本机 Read/git 去「核实」业务仓（会与 2017 打架）  
- 业务仓开工程师模式旁路改码（须定稿转任务）  
- sidecar `ssh mac2017` 探/写业务仓（走 Hub 只读透镜）

权威契约：[`loop-engineer-authority.md`](loop-engineer-authority.md)。

详步骤与反例 → [`app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md) · 五仓清单 → [`fleet-apps-migration-2026-07.md`](../deploy/fleet-apps-migration-2026-07.md)。
