# Mac2017 服务端目录规范

> SSOT：Server 机 `~/program` 布局。禁止随意新建顶层业务目录。  
> 机器：`fan@192.168.3.116`（SSH host `mac2017`）

---

## 根路径

**`/Users/fan/program`**

不换根名（与习惯/文档一致）；**内容按本规范重组**，不软链 M1。

```text
/Users/fan/program/
  README.md                 # 本机三句话说明 → 指向本文
  CCC/                      # 主产品 + orch（唯一编排仓）
  infra/
    ai-loop-router/         # 已退役（归档）；勿再 launchd 启用 :4000/:4002
  apps/
    ccc-demo/               # 默认 demo
    clawmed-ccc/            # 垂直产品（测试中）
    xianyu/  qb/  qx-observer/  hp/  medio-0/   # 舰队业务仓
  archive/
    YYYY-MM-DD-*/           # 冷数据 / 半同步残骸
```

**Hub `project_id`**：通常 = `apps/` 目录名；**例外**：路径 `apps/qx-observer` 的 Hub id = **`qxo`**（Board 发现别名，见 [`fleet-apps-migration-2026-07.md`](fleet-apps-migration-2026-07.md)）。`medio-0` 小写。

---

## 规则

| 路径 | 用途 | 规则 |
|------|------|------|
| `CCC/` | 产品代码、Hub/Engine、文档、`vendor/` | 唯一主仓；不在仓外散落产品代码 |
| `infra/ai-loop-router/` | 历史中转（已退役） | **不** register；plist 已移至 `LaunchAgents/disabled-relay-*` |
| `apps/<name>/` | 经 doctor register 的业务仓 | **新项目必须落这里**；**唯一代码权威** |
| `archive/` | 冷存 | 不参与 Engine 登记 |
| 其他顶层目录 | — | **禁止**；先改本文再创建 |

---

## 新项目流程

1. `mkdir -p ~/program/apps/<name> && cd ... && git clone …`（或 init）  
2. 在 Server 上：`python3 ~/program/CCC/scripts/ccc-init.py ~/program/apps/<name> --register`  
3. `python3 ~/program/CCC/scripts/ccc-workspace-doctor.py`  
4. M1 Desktop：刷新项目列表 → 点项目卡对话（对齐基线走 Hub；**不**再要求本机业务 clone）  

单仓清单：[`../runbooks/app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md)  
五仓舰队迁移（运维）：[`fleet-apps-migration-2026-07.md`](fleet-apps-migration-2026-07.md)  
Agent 短交接：[`../product/desktop-agent-handoff.md`](../product/desktop-agent-handoff.md)

---

## 与 M1 客户端

```text
代码权威 = 本机 apps/<name>（已 register）
远端备份 = GitHub
M1 对话  = Desktop + sidecar；事实只信 Hub baseline；无业务源码第二树
M1 平台  = ~/program/CCC（Cursor 改 CCC；localWorkspaceMap 仅可映 ccc）
```

- **生产执行、Hub/Engine** 以 2017 为准（模型直连 MiniMax / 讯飞；中转已退役）  
- **M1 对话**：Desktop + sidecar `:7788` + arm64 `vendor/loop-code/cli` → MiniMax  
- **Mac2017 不再部署 loop-code 二进制**（Hub `/api/chat` 已删，2017 不做对话）
---

## 清理原则

半同步/残缺副本 → 移入 `archive/YYYY-MM-DD-preserver/`，再按需删除。  
不在生产路径上「接着用旧半吊子 clone」。  
**M1 不保留业务仓副本或 m1-freeze 工作区**（干扰双权威）。
