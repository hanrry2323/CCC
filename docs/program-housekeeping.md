# program 目录整理（服务端规范优先）

> **服务端（Mac2017）布局以 [`deploy/server-layout.md`](deploy/server-layout.md) 为 SSOT。**  
> 本文保留客户端/历史整理原则；与 server-layout 冲突时以 server-layout 为准。

---

## 服务端（Mac2017）强制结构

```text
/Users/fan/program/
  CCC/
  infra/ai-loop-router/
  apps/<name>/          # 新业务只许落这里
  archive/
  README.md
```

禁止在 `~/program` 顶层随意新建业务仓。新项目流程见 server-layout。

---

## 原则（通用）

1. **要跑 Engine 的仓** → 登记 `workspaces.json`（Server 上），路径落在 `apps/`。  
2. **归档 / 半同步残骸** → `archive/`，不参与登记。  
3. **不把业务仓并进 CCC git**；产品代码只在 `CCC/`。  
4. **不软链跨机**（M1 ↔ 2017）；需要则 clone/拷贝。

---

## 客户端机（M1）

可保留个人多仓作移动开发；**生产 Hub/Engine/中转以 2017 为准**（见 [`deploy/topology.md`](deploy/topology.md)）。

历史舰队列表示例仅作「如何注册」参考，**不是产品默认态**。默认态见 [`product/reset-demo-fleet.md`](product/reset-demo-fleet.md)。

---

## 卫生命令

```bash
python3 scripts/ccc-workspace-doctor.py
python3 scripts/ccc-workspace-doctor.py list
```

---

## 归档步骤

1. `mkdir -p ~/program/archive/YYYY-MM-DD-label`  
2. `mv <path> ~/program/archive/YYYY-MM-DD-label/`  
3. `unregister` 对应登记  
4. 更新 `.ccc/infrastructure.md`（若影响端口/角色）  
