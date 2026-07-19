# Desktop Agent 交接：业务仓迁移与接入

> **给 Desktop / Hub Agent 的短交接**（迁移、注册、开项目对话）。  
> 完整步骤 SSOT：[`../runbooks/app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md)。  
> 触发：「迁移到 2017」「接入 CCC」「桌面端怎么打开项目」「下一步做什么」。

---

## 你必须先懂的边界

1. **编排 SSOT = Mac2017** `~/program/apps/<name>`（规范：进 `apps/`，勿顶层乱放）。  
2. **对话 = M1 Desktop + sidecar**；cwd 必须是 **M1 本机路径**（`ccc.localWorkspaceMap`）。  
3. **一项目一对话**：`{project_id}::main`；点项目卡即进入；「重置」≠ 新建 thread。  
4. **CCC orch 不可下达**；只对 `role=app` 且已 register 的仓转任务。  
5. **红线 12**：不擅自 `enable` 控制面。

---

## 迁移「完毕」后强制下一步（按序）

```text
落盘 apps/<name> → ccc-init → --register → doctor
→ 告知用户配置 M1 localWorkspaceMap
→ Desktop 刷新 → 点项目卡验证对话
→（用户要自动跑时）再提 enable —— 等用户点头
```

### Mac2017（SSH `fan@192.168.3.116`）

```bash
# 例：clawmed-ccc
test -d /Users/fan/program/apps/clawmed-ccc/.git || echo "尚未落到规范路径"
python3 /Users/fan/program/CCC/scripts/ccc-init.py /Users/fan/program/apps/clawmed-ccc
python3 /Users/fan/program/CCC/scripts/ccc-init.py /Users/fan/program/apps/clawmed-ccc --register
python3 /Users/fan/program/CCC/scripts/ccc-workspace-doctor.py
python3 /Users/fan/program/CCC/scripts/ccc-sync-agent-roots.py
```

### M1 Desktop

1. 本机副本存在（如 `/Users/apple/program/clawmed-ccc`）。  
2. 设置 `localWorkspaceMap`：`"clawmed-ccc" → 本机绝对路径`。  
3. 侧栏出现项目卡 → 点击 → 中间栏即该项目对话框。  
4. 用户路径：对齐基线 → 定稿 → 转任务。

### 验收（你要能回报）

| 检查 | 期望 |
|------|------|
| 2017 `apps/<name>` | 存在且有 `.ccc/board` |
| `~/.ccc/workspaces.json` | 有该 app，`engine_eligible`/`engine` 合理 |
| `GET /api/desktop/projects` | 列表含该 `project_id` |
| Desktop 点卡 | 进入 `{id}::main`，sidecar 健康可聊 |

---

## 对用户怎么说（口径）

- 「代码在 2017 编排；你在 Desktop 点项目卡聊；转任务后 Engine 在 2017 跑。」  
- 「一个项目只有一个对话；不要找第二个聊天窗口。」  
- 「没在侧栏出现 = 还没 init/board 或 Hub 未刷新；能聊不能下任务 = 还没 register。」

---

## 禁止

- 只搬文件就宣布完成  
- 对 CCC 仓下业务 epic  
- 擅自 enable Engine  
- 发明多 thread / 「再开一个项目对话框」  
- 把业务仓塞进 `~/program/CCC` 或 `archive/` 当生产路径  

详步骤与反例 → [`app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md)。
