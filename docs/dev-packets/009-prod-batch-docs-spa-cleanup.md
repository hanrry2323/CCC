# 009 · 大批次：文档对齐 + SPA 残留清理

> **模式**：一次会话多阶段 · 一条总回报  
> **分支**：`draft/prod-batch-docs-spa-cleanup`（从最新 `main`）  
> **黑名单**：`upstreams.json` · `~/.ccc/**` · Dual-host · push main · Desktop Agent 改 CCC

## 总目标

生产级门禁前把「文档与网页残留」收齐：入口文档不再把网页看板/运维当主路径；设置页去掉已默认关闭的 Agent Token 误导；控制台保留但标明兜底。

**禁止**改 Engine 调度核心、权威 SSOT 大段重写（可小补交叉引用）。

---

## Phase A — GO-LIVE / Hub 远程文档对齐

读：
- `docs/GO-LIVE-DESKTOP.md`
- `docs/product/hub-remote-management.md`
- `docs/product/desktop-ops-ux.md`（对照）

改：
1. 凡写「打开 Hub `#/board` / `#/ops` 做日常」→ 改为 **CCC Desktop 左侧看板 / 运维**。
2. 网页 `#/board` `#/ops` 标为 **停更兼容**；应急用 `#/console`。
3. 若文档仍写 Agent Token 必填 / `CCC_AGENT_AUTH=1` 为默认 → 改为 **默认 `CCC_AGENT_AUTH=0`**，Token 仅加固可选。
4. 不写长教程；改口径 + 加一句「权威见 desktop-ops-ux / authority」。

**验收**：文档检索「日常用网页看板」「必须填 Agent Token」类表述消失或标明过时。

---

## Phase B — settings.js 去掉 Token 误导

读：`scripts/chat_server/frontend/js/pages/settings.js`（及调用处）

改：
1. 隐藏或弱化「Agent Token」主路径设置（默认无 auth）。
2. 可保留折叠「加固（可选）」说明：仅当运维显式 `CCC_AGENT_AUTH=1` 时需要。
3. 不删整个设置页；不改 sidecar 代码（除非发现明显死链文案）。

**验收**：设置页不再暗示「必须填 Token 才能对话」。

---

## Phase C — console 页顶栏兜底说明

读：`scripts/chat_server/frontend/js/pages/consolePage.js`（或等价）

改：页顶加短横幅（一行即可）：
「控制台为 SSH/应急兜底；日常看板与运维请用 CCC Desktop。」

**验收**：打开 `#/console` 可见该说明；功能不删。

---

## Phase D — README / INDEX 小指针（可选）

若 `README.md` 或 `docs/INDEX.md` 仍把 Hub SPA 看板写成产品主入口：改一行指向 Desktop。没有则跳过并在回报写 skip。

---

## 总验收

```bash
cd ~/program/CCC
git checkout -B draft/prod-batch-docs-spa-cleanup origin/main
# …全部 Phase 后…
node --check scripts/chat_server/frontend/js/pages/settings.js
# 若改了 console：
node --check scripts/chat_server/frontend/js/pages/consolePage.js 2>/dev/null || true
git log --oneline origin/main..HEAD
```

## 总回报格式

```
BRANCH: draft/prod-batch-docs-spa-cleanup
COMMITS: …
FILES: …
PHASES: A/B/C/D = pass|fail|skip — …
TESTS: …
RESIDUAL: …
```

---

## 会话开场（整段粘贴）

```
你是 CCC 草稿工。任务卡：docs/dev-packets/009-prod-batch-docs-spa-cleanup.md
分支 draft/prod-batch-docs-spa-cleanup（从最新 main）。
按 A→B→C→D 顺序做完再一条总回报。
可自行 commit。禁止 push main、黑名单、改 Engine 核心。
开始前 git fetch && checkout -B … origin/main。
```
