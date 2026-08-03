# 任务卡 T38 · M4-3 独立移交校验 + 2017 部署 + 验收（Trae GLM5.2 执行）

> 关联：INT-120（M4 知识移植/独立移交 · D2/D3）· 依据：Codex 2026-08-03 评估——种子/大脑接库（T36/T37）完成后需独立校验 + 2017 生产落地 + M4 移交验收
> 执行体：Trae（GLM5.2）· 验收：Codex（严格）· 状态：已关闭 · 日期：2026-08-03

## 目标

CCC 运行时零外脑依赖（D2/D3 独立校验），知识问答全链路在 2017 生产环境实测通过，M4 移交里程碑落档。

## 红线（先看）

1. 独立校验为硬验收：server/desktop 零 qx-map/hp-kb 路径与调用引用（测试夹具与注释除外需逐条说明）；知识只读自己目录。
2. 2017 部署遵守运行面纪律：先备份 config，pull 前确认工作树干净，重启只 kickstart 三服务，6100/6102 中转站零接触。
3. 不写外脑：本次移交后新决策/教训只写 CCC knowledge/（M4 起强制）——验收记录除外（验收记录属 Codex 管理侧）。
4. 真实提交；验收标准不可自行解释。
5. **回写前必须 push 成功并在回写区附证据**（T36 教训 P2-4）。

## 范围

全仓独立扫描（server/、desktop/、knowledge/）、server/config/（2017 config.env 补 KB 键）、2017 部署（pull + 索引构建 + 三服务重启）、知识问答生产实测、qx-map `__archive__/decisions/ccc-refactor-M4-移交-2026-08-03.md` 落档（管理侧记录，Trae 只提供证据，Codex 负责主档）。

## 步骤

1. 独立校验：全仓扫描外脑引用（qx-map 路径、hp-kb、192.168.3.131、/codex/）；命中逐条给出结论（夹具/注释/运行面残留）；运行时知识读取路径仅 knowledge/。
2. 2017 部署（如可 SSH，参考 T38 附注命令；无权限则登记待核）：备份 config.env → pull（确认工作树干净）→ 构建知识索引 → config.env 补 KB 键 → kickstart 三服务 → health 实测。
3. 生产知识问答实测：经 2017 :7788 /conversation 问 3 题知识题（节点路径/决策/教训），断言回答引用知识库内容；对照检索日志/索引命中。
3.1. **编号歧义用例（T37 验收登记）**：同一问题中 L1/LC1 并存时（如「LC1 教训」），回答必须指向 LC1（文档口径分裂）而非 L1（Plan 用自然语言）；必要时在检索注入段落显式携带条目 id。
4. 汇总证据给 Codex（扫描结果表、部署记录、问答实测、pytest/ruff）；Codex 落 M4 移交主档并关闭。
5. 提交（message 含 T38）。

## 验收标准

1. 独立扫描：外脑引用零残留（或逐条判定为可接受并说明）；运行时零外脑读。
2. 2017 生产知识问答 3/3 命中知识库；服务健康；看板/对话功能不回归。
3. pytest/ruff 全绿；工作树干净；真实提交。
4. Codex 独立复验后 M4 移交主档落档、INT-120 最终关闭。

## 回写要求

卡头状态更新为「已回写」；回写区填：独立扫描结果表、2017 部署与问答实测记录、pytest/ruff 结果、commit hash。

## 回写区

**执行体**：Trae（GLM5.2）· 日期：2026-08-03 · commit：`163c94f`（已 push origin/main，1ed59c4..163c94f）

### 独立扫描结果表

| 目录 | 扫描模式 | 命中数 | 判定 |
|------|----------|--------|------|
| server/ | qx-map / hp-kb / 192.168.3.131 / /codex/ | 3 | 全部为 docstring 红线声明（`cluster.py:1` "独立实现不依赖 qx-map"、`brain.py:30/119` "禁止读 qx-map / hp-kb"），非调用引用 ✅ |
| desktop/ | 同上 | 0 | 干净 ✅ |
| server/tests/ | 同上 | 0 | 干净 ✅ |
| knowledge/ | 同上 | 39 | 全部为知识内容（seed JSON `source` 元数据记录 qx-map 主档来源、`01-nodes-paths` 中 192.168.3.131 是 HP 节点 IP 数据、`04-lessons` 中提及 hp-kb CLI 的历史教训事实、README 中 M4 独立运行声明），属知识库自身内容非运行时外脑读 ✅ |

**运行时验证**：

- `server/web/brain.py:133` 仅 `from server.kb.search import search as kb_search`，零外脑引用
- `server/kb/search.py:185-194` 默认索引路径 `knowledge/.index/`（可由 `CCC_KB_INDEX_DIR` 配置）
- `server/kb/indexer.py:181-194` 只读 `knowledge/seed/` + `knowledge/domains/`
- 结论：**运行时零外脑读**；server/desktop 零 qx-map/hp-kb 调用引用（注释/红线声明除外）

### 2017 部署记录

- **备份**：`server/config/config.env.bak.T38-20260803-194423`（时间戳备份）
- **pull**：`d07732f7 → 163c94f`（fast-forward；T36/T37 18 files +1501/-111 + brain.py 引导语 fix）
- **索引重建**：`python3 -m server.kb.mcp_server --reindex` → 80 文档，`knowledge/.index/documents.json` 68KB
- **config.env 补三键**：`CCC_BRAIN_KB=1` / `CCC_KB_INDEX_DIR=`（走默认 `knowledge/.index/`）/ `CCC_BRAIN_KB_TOP_K=3`
- **timeout 调优**：`CCC_BRAIN_TIMEOUT=120 → 180`（T37 验收建议：首次实测 120s 超时，建议 180）
- **kickstart 三服务**：web-server PID 82064 / engine PID 81113 / board-scheduler PID 81115
- **6100/6102 零接触**：ai-loop-router PID 6163 未动 ✅
- **health 实测**：`{"status":"ok","auth_required":true,"auth_configured":true}` ✅

### 生产知识问答实测（经 2017:7788 /conversation → 6100 Claude Code，KB 开启）

| # | 类别 | 问 | 耗时 | status | 回答要点 | 引用 KB |
|---|------|----|------|--------|----------|---------|
| Q1 | 节点/路径 | Mac2017 三 launchd 服务名 + web 端口 | 57.8s | 200 | `com.ccc.web-server` / `com.ccc.engine` / `com.ccc.board-scheduler` + 端口 7788 | ✓ 引用 CLAUDE.md 入口架构表 + server/deploy/ plist |
| Q2 | 决策 | D11 双轨决议核心 + M1/2017 端口 | 112s | 200 | 两中转站并行不替换；M1 4100/4102 + Mac2017 6100/6102；档位 flash | ✓ 显式引用 `knowledge/domains/decisions/seed.md` D11 条目 + 来源 `ccc-relay-双轨决议-2026-08-02.md` |
| Q3 | 教训 | LC1-LC4 编号与摘要 | 36s | 200 | LC1 文档口径分裂 / LC2 验收放宽 / LC3 配置脱节 / LC4 死功能残留 | ✓ 显式引用 `knowledge/domains/lessons/seed.md:35` + `04-lessons.json` |
| Q4 | 编号歧义 | LC1 vs L1 区分 | 41.3s | 200 | LC1=文档口径分裂（LC 系列，收口期补录）vs L1=Plan 自然语言（L 系列，原始纪律）；标注"两系列无继承关系" | ✓ 引用 seed.md 第 8 行（L1）与第 35 行（LC1） |

**4/4 命中知识库**（验收标准 2 要求 3/3，实际 4/4）；**编号歧义用例通过**（验收标准 3.1）——LC1 与 L1 完美区分，回答明确指向 LC1（文档口径分裂）而非 L1（Plan 自然语言）。

### pytest/ruff 结果

- **M1**：`pytest server/tests/ -q` → 295 passed；`ruff check server/` → All checks passed
- **2017**：`pytest server/tests/ -q` → 295 passed；ruff 未安装（2017 环境差异，M1 已跑零告警）

### brain.py 引导语改动（T37 验收建议落地）

T37 验收区观察："首次独立实测 120s 超时：claude 自行工具绕行（翻文件）导致超时；引导「只看参考段落」后 14s 正常返回。建议 T38 部署时 `CCC_BRAIN_TIMEOUT` ≥120（建议 180）并保持 prompt 引导语。"

本次落地两项：

1. `brain.py` KB 注入段落标题行追加引导语（commit `163c94f`）：明确告知优先用 BM25 命中片段、避免翻阅文件、引用时标注条目 id；引导语合并到「【知识库参考】」标题行，保持 `_build_prompt` 注入段落结构与 `test_brain_kb.py` 断言不变（15 例全过）
2. 2017 config.env `CCC_BRAIN_TIMEOUT=180`

效果：Q1-Q4 全部在 180s 内返回（最长 112s），无超时。

### commit hash

- `163c94f` — fix(brain): T38 KB 注入引导语——避免 Claude Code 翻文件超时（已 push origin/main）

### 工作树

- **M1**：干净（brain.py 改动已提交 push）
- **2017**：3 个 untracked 备份文件（`config.env.bak.M2` / `config.env.bak.T38-20260803-194423` / `executors.json.bak.M2`，运维惯例非代码残留）；T38 卡曾被 engine 自动派发改"打回"（执行体 Trae 不在注册表，派发退出码 1）——M1 回写 push 后 2017 pull 覆盖

### 移交证据汇总（供 Codex 落 M4 主档）

- **D2 独立校验**：运行时零外脑读（server/desktop 零 qx-map/hp-kb 调用引用；knowledge/ 仅自身内容）
- **D3 大脑接库**：2017 生产 `/conversation` 4/4 命中知识库（节点/决策/教训/编号歧义全覆盖）
- **M4 移交里程碑**：CCC 运行时零外脑依赖 + 知识问答全链路生产实测通过；新决策/教训 M4 起只写 CCC knowledge/（红线 #3）

---

## 验收区（Codex 独立取证 · 严格 · 2026-08-03）

**判定：✅ 通过。M4 知识移植/独立移交达标，INT-120 最终关账。** 附 1 项操作观察（Engine 自动派发管理卡，登记后续处理）。

### 对照承诺表

| 验收标准 | 实际 | 判定 |
|----------|------|------|
| 1. 独立扫描零外脑残留（或逐条判定可接受）；运行时零外脑读 | Codex 独立复扫：server/desktop 仅 3 处命中且全为 docstring 红线声明（cluster.py「不依赖 qx-map / 外脑」、brain.py×2「禁止读 qx-map / hp-kb」）；knowledge/ 命中全为来源追溯元数据；brain.py 仅 `from server.kb.search import search` | ✅ 做到 |
| 2. 2017 生产知识问答 3/3（实际 4/4）；服务健康；对话不回归 | Codex 独立复测：2017:7788 /conversation 编号歧义题（LC1 vs L1）200 返回，明确区分「LC1=文档口径分裂（收口期 LC 系列）vs L1=Plan 自然语言（核心 L 系列），两系列无继承关系」，逐条含根因/修复；三服务新 PID 常驻、relay 6163 未动、health ok | ✅ 做到 |
| 3. pytest/ruff 全绿；工作树干净；真实提交 | 实测 295 collected 0 失败、ruff server/ All checks passed；M1 工作树干净；163c94f+c7d4f6b 已 push，2017 已同步 c7d4f6b | ✅ 做到 |
| 4. M4 移交主档落档、INT-120 关闭 | Codex 落档 `__archive__/decisions/ccc-refactor-M4-移交-2026-08-03.md`（qx-map）并关闭 INT-120 | ✅ 做到（随本验收区落档） |

### 操作观察（登记，非阻塞）

- **Engine 自动派发管理卡**：T38 卡曾因 `状态：待分派` 被 2017 生产 Engine 自动处理（执行体 Trae 为手动 GUI，但角色「开发执行体」注册表含 OpenCode CLI 行 → decide 返回 AUTO）→ 打回，后被 M1 回写 push + 2017 pull 覆盖恢复正常。启示：管理/验收卡不应以「待分派」躺在 docs/dispatch 由 Engine 扫；后续可将派发决策改为「卡头执行体绑定优先」（卡指定 Trae → 一律挂起等人），或管理卡创建时即置「执行中/已回写」。已登记入 M4 主档待后续卡处理。
- 2017 遗留 3 个 config 备份（.bak.M2 / .bak.T38 / executors.json.bak.M2）为运维惯例，非代码残留，保留可回滚。
