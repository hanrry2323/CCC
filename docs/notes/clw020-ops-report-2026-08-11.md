# 定时运维巡检报告 (clw020-ops-report)

> 巡检日期：2026-08-11  
> 执 行 体：W9（运维专家）  
> 触发源：scheduler 定时触发  
> 验证性质：非绑定任务·定时运维首端到端样例

---

## 一、集群三机连通性巡检

本项巡检对照 qx-map `cluster/cluster.json` 与 `projects/manifest.md` 记录的状态，并结合实际网络连通性进行验证：

### 1. 节点状态汇总

| 节点 ID | 机器名 | IP 地址 | 状态 | 角色定义与服务 | 证据 / 数据源 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **M1** | m1.local | 192.168.3.140 | ✅ 活跃 | 大脑机 + 开发分担机；运行 Postgres 等 | `manifest.md` 第 48-75 行，Load: 2.10 |
| **Mac2017** | fan.local | 192.168.3.116 | ✅ 活跃 | 唯一中转站 + 重活节点；:7788 web-server 活跃 | `manifest.md` 第 78-106 行，Load: 15.51 |
| **HP** | hp-server | 192.168.3.131 | ✅ 活跃 | 知识库服务；运行 mcp-server :8083, pg :5432, ollama | `manifest.md` 第 109-148 行，Load: 0.07 |
| **Windows / 252** | win | 192.168.3.252 | ❌ 离线/SSH不可达 | 备用节点；SSH 连通性 ❌，延迟 0.0ms | `manifest.md` 第 16 行 & `cluster.json` 第 67 行 |

### 2. 结论与证据
- **结论**：集群核心三机（M1 / Mac2017 / HP）保持 100% 连通与服务高可用；252 (Windows) 终端处于只读消费且 SSH 处于不可达状态（延迟 0.0ms 且 SSH: ❌），与 `cluster.json` 中标记的 `"reachable": false` 契合。
- **证据文件**：
  - `/Users/fan/program/qx-map/cluster/cluster.json` (第 67 行: `"reachable": false`)
  - `/Users/fan/program/qx-map/projects/manifest.md` (第 16 行: `| Windows | 192.168.3.252 | ❌ | 0.0 ms | win@ |`)

---

## 二、Roadmap 漂移巡检

本项巡检对照 `docs/roadmap.md` 中的业务线路描述与看板（任务卡）的真实完成状态：

### 1. 巡检结果分析

- **clw 业务线路漂移**：
  - `docs/roadmap.md` 的 `业务线路（clw）` 表格（第 435-447 行）目前仅记录了 `clw001` 到 `clw007` 的状态，其中 `clw004` 与 `clw005` 仍被标注为 `未合入 main（分支孤岛）`。
  - **实际漂移**：事实上，`clw008` 至 `clw019` 在看板上已经全部合入并标记为 `已关闭` (已回写且通过验收)，且 `v0.2.0`（2026-08-11）已经全量重构发布。
  - **严重缺失**：`docs/roadmap.md` 里的 clw 业务表格没有任何 `clw008` ~ `clw019` 的条目（仅在文本说明中有零散提及，且 `clw019` 甚至完全没有被提及），导致路线图在 v0.2.0 发布后严重漂移。
- **其他项目 (xy/hp/mx/qb) 校验**：
  - `xy` 线路（第 147-207 行）：表格列出的 `xy009` ~ `xy013`、`xy016` ~ `xy020`、`xy021` ~ `xy031` 的状态与看板全量一致，均已关闭。
  - `hp` 线路（第 210-237 行）和 `mx` 线路（第 242-279 行）登记与实际卡状态（全部已关闭）100% 保持一致，无漂移。

### 2. 结论与证据
- **结论**：`docs/roadmap.md` 在 **clw（统一桌面）** 线路存在显著的路线图漂移。v0.2.0 与 v0.3.0 相关的大量已关闭卡片（clw008 ~ clw019）未更新填充到 `clw 业务线路` 表格中，严重滞后于开发实际。
- **证据文件**：
  - `/Users/fan/program/ccc-dev-ws-clw020/docs/roadmap.md` (第 435-452 行，表格缺失大量已合入卡片)
  - `/Users/fan/program/CCC/docs/dispatch/clw/` 下 `clw008-p0-exec-chain-fix.md` ~ `clw019-ui-role-inject-verify.md` 均处于 `已关闭` 状态。

---

## 三、Worker 登记一致性巡检

本项巡检对比 `command-post/workers.md` 中的登记画像与集群内执行任务的实际 Worker 实例：

### 1. 巡检结果分析

- **W9 缺失问题**：
  - 本次定时任务 `clw020` 由 `scheduler` 指派给 `W9 = 252 移动终端 Claude Code`。
  - **实际不一致**：在权威 Worker 登记表 `/Users/fan/program/qx-map/command-post/workers.md` 中，登记列表只录入到 `W1` ~ `W8`，**完全缺失 W9 的登记记录**。
  - **说明不匹配**：虽然方案 `020-cluster-worker-pool.md` 已经大范围讨论了 `252` 接入并标号为 `W9`，但画像登记表却未能及时同步，属于明显的登记漏登与配置漂移。

### 2. 结论与证据
- **结论**：Worker 登记表 `workers.md` 存在一致性漂移。W9（252 移动终端 Claude Code）作为已被实际指派定时运维和部分设计卡（clw019）的核心 Worker，目前处于“无证驾驶”状态，登记表未予正式注册。
- **证据文件**：
  - `/Users/fan/program/qx-map/command-post/workers.md` (第 23-32 行，仅含 W1~W8，无 W9 记录)
  - `/Users/fan/program/CCC/docs/dispatch/clw/clw020-scheduled-ops-verify.md` (第 3 行: `执行体：W9`)

---

## 四、运维优化建议

针对上述三项巡检结果，提出以下改进和修复建议：

1. **注册 W9 角色**：在 `/Users/fan/program/qx-map/command-post/workers.md` 登记表中，正式补齐 `W9` 这一行（实例：Claude Code, 机器：Windows/252, 能力标签：`dev, ops, review`，状态：活跃），对齐 020 方案中的权限。
2. **对齐 clw 路线图**：更新 `docs/roadmap.md`，在 `业务线路（clw）` 下补充 `clw008` 到 `clw019` 的表格，将其状态标为 `已关闭`，以消除路线图严重滞后的漂移。
3. **修复 252 SSH 可达性**：核实 252 节点的 SSH 服务配置或网络路由限制，必要时开启 SSH 访问以便实现双向连通和直接调试。
