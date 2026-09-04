# 中枢了解项目 SOP（出卡前）

> **权威入口**：[`docs/INDEX.md`](../INDEX.md) §0 · [`DOC-PROTOCOL.md`](../DOC-PROTOCOL.md)  
> **心智摘要**：[`AGENTS.md`](../../AGENTS.md) · [`CLAUDE.md`](../../CLAUDE.md)  
> **目的**：几分钟内摸清边界与进度，精准出卡；**禁止每次满仓漫游**，也**禁止把「禁 ssh 业务仓」误读成「不能了解代码」**。

---

## 0. 一句话

**扫 CCC = 在 2017 权威仓本地读；进度 = 看板 + 未关闭卡；业务仓 = 档案 + 卡内探针（不 ssh 翻仓）；了解 ≠ 代执行。**

---

## 1. 允许 / 禁止（与 AGENTS / CLAUDE 同表）

| 对象 | 允许 | 禁止 |
|------|------|------|
| **CCC 本仓**（仓库根 = 本文件所在仓） | 本地读码、`pytest`/`ruff`、`git log`、codebase-memory、看板 API（端点见 `docs/deploy/topology.md`）、KB | 代执行体分支 commit/push；手改 2017 运行面 |
| **2017 平台核验** | 只读 ssh（`ps`/`lsof`/`ls`/`cat` 日志、`git log -1`、health） | 手改生产；非部署 SOP 代 pull/重启 |
| **业务仓**（qb/xy/mx…） | `docs/projects/<prefix>/README.md` + KB；核实步骤写进卡 | ssh 连环侦察；代跑业务测；代 commit/push；先做完再出卡 |

---

## 2. 固定 6 步（≤几分钟）

出卡 / 扫 bug / 「先做 X」时按序做；做完即落卡，勿再开支线考古。

### ① 身份

```bash
cd <仓库根> && cat VERSION && git log -5 --oneline
```

cwd 不是本仓 → **当面点破**，禁止当成 CCC 继续。

### ② 项目边界

1. 读 [`docs/projects/registry.yaml`](../projects/registry.yaml)（前缀 / `taskable` / `paths` / `forbidden`）。  
2. 读目标 [`docs/projects/<prefix>/README.md`](../projects/)（路径、禁区、近况一行）。  
3. 扫 [`docs/projects/<prefix>/plans/`](../projects/) 已有方案，避免重复规划。  
4. `qh` / `forbidden: true` → 不出卡，按 registry 改门禁。

### ③ 进度（SSOT = 卡 + 看板）

- 人看 / 机读：看板端点与路径**只认 `docs/deploy/topology.md`**（机器名/端口不写死）；机读 `GET <board>/board/states`（或 `/cards`）  
- 扫 `docs/dispatch/<prefix>/` **未关闭**卡，避免重复出卡  

**禁止**全文 grep「待分派」当进度；无 `GET /board` 根路径。

### ④ 知识

- 仓内 `knowledge/` / KB 检索，或 hp-kb 按项目域（决策 / 红线）。  
- 结论用于出卡验收点；**禁止**复制成长文新文档（落点见 DOC-PROTOCOL）。

### ⑤ 代码地图

| 场景 | 做法 |
|------|------|
| 前缀 `ccc` / 改本仓 | codebase-memory 或定向 `rg` / 读相关测；可跑本仓 `pytest`/`ruff` 取证 |
| 业务仓（2017 权威仓；M1 无树） | **不 ssh 翻仓**；卡内写：`cwd=<registry.paths.mac2017>` + 核实探针（`git status` / 指定文件存在等） |
| 2017 平台是否活着 | 只读：`curl :7788/health`；必要时 ssh `launchctl list \| grep com.ccc` |

### ⑥ 落卡

1. 目标一句 + 红线 + 可观察验收点 +（若需）业务仓探针。  
2. `scripts/new-card.sh --project <prefix> --title "…"`（可先 `--dry-run`）。  
3. validate → **只提交任务卡** → `push origin main`。  
4. **停手盯板**。

缺的是老板意图/红线 → 只问 **一句**；本仓长什么样 → 回到 ⑤，别问老板。

---

## 3. 反模式

| 反模式 | 正解 |
|--------|------|
| 「禁止 ssh」→ 不敢扫 CCC | CCC 在 M1 本地扫 |
| ssh qb/xy 连环 `find`/`pytest` 再出卡 | 档案 + 卡内探针，执行体核实 |
| 每次从 `VISION.md` / 全仓重读 | 只走本 SOP 6 步 |
| 为写准卡代跑业务全量测 / 代 commit | 出卡 ≠ 代执行 |
| 卫生欠账自己 ssh 清脏 | 出极窄维护卡（见 CLAUDE 卫生段） |
| 全文搜「待分派」当看板 | `/board/states` 或看板 UI |

---

## 4. 相关

- 开发通道：[`dev-channel.md`](dev-channel.md)  
- 终验：[`accept-board-sop.md`](accept-board-sop.md)  
- qb 反模式：[`../../references/transfer-playbook-qb.md`](../../references/transfer-playbook-qb.md)  
