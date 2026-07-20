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
    ai-loop-router/         # 唯一生产中转
  apps/
    ccc-demo/               # 默认 demo
    clawmed-ccc/            # 垂直产品（测试中）
    xianyu/  qb/  qx-observer/  hp/  medio-0/   # 舰队业务仓
  archive/
    YYYY-MM-DD-*/           # 冷数据 / 半同步残骸
```

**Hub `project_id`** = `apps/` 下目录名（`qx-observer` 不用 `qxo`；`medio-0` 小写）。

---

## 规则

| 路径 | 用途 | 规则 |
|------|------|------|
| `CCC/` | 产品代码、Hub/Engine、文档、`vendor/` | 唯一主仓；不在仓外散落产品代码 |
| `infra/ai-loop-router/` | 模型中转 | 中转只此一处；**不** register 为 Engine app |
| `apps/<name>/` | 经 doctor register 的业务仓 | **新项目必须落这里**；主力开发在此 |
| `archive/` | 冷存 | 不参与 Engine 登记 |
| 其他顶层目录 | — | **禁止**；先改本文再创建 |

---

## 新项目流程

1. `mkdir -p ~/program/apps/<name> && cd ... && git clone …`（或 init）  
2. 在 Server 上：`python3 ~/program/CCC/scripts/ccc-init.py ~/program/apps/<name> --register`  
3. `python3 ~/program/CCC/scripts/ccc-workspace-doctor.py`  
4. M1：`git clone` 到 `~/program/apps/<name>` + Desktop `localWorkspaceMap`；点项目卡进入对话  

单仓清单：[`../runbooks/app-migrate-register-desktop.md`](../runbooks/app-migrate-register-desktop.md)  
五仓舰队迁移（运维）：[`fleet-apps-migration-2026-07.md`](fleet-apps-migration-2026-07.md)  
Agent 短交接：[`../product/desktop-agent-handoff.md`](../product/desktop-agent-handoff.md)

---

## 与 M1 客户端

```text
编排 SSOT = 本机 apps/<name>
对话 cwd  = M1 ~/program/apps/<name>（瘦 clone + localWorkspaceMap）
M1 archive/*-m1-freeze/ = 只读备份，禁止 register
```

- **生产执行、中转、Hub/Engine** 以 2017 为准  
- **M1 对话**：Desktop + sidecar `:7788` + arm64 `vendor/loop-code/cli`（M1 本机；gitignore）  
- **Mac2017 不再部署 loop-code 二进制**（架构对齐 2026-07-19；Hub `/api/chat` 已删，2017 不做对话）
---

## 清理原则

半同步/残缺副本 → 移入 `archive/YYYY-MM-DD-preserver/`，再按需删除。  
不在生产路径上「接着用旧半吊子 clone」。
