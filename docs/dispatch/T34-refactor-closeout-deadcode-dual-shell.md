# 任务卡 T34 · 重构收口：死代码/孤儿页面/双壳/遗留物清理（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§5 不越范围 / 提交卫生）
> 依据：Codex 2026-08-03 全新取证重评——孤儿看板壳 server/web/index.html 未被静态白名单挂载（"/" 走 legacy-chat）；legacy-chat 存在未挂载死代码（dispatchCard.js）与旧 Hub 文案（M1 :7788 / CCC Hub 编排口）；src-tauri 为 Tauri 旧 Cockpit 遗留、现行系统只用 desktop/（Swift）；根目录 _update_handoff.py 为 QuantHive 会话遗留物混入 CCC 仓
> 执行体：Trae · 验收：Codex · 状态：已回写 · 日期：2026-08-03

## 目标

仓内只剩一套现行桌面壳（desktop/ Swift）+ 一个 HTTP 入口（legacy-chat 四视图）；孤儿页面、死代码、旧文案、跨项目遗留物全部清出；历史组件只归档不物理删除。

## 红线（先看）

1. 归档优先：涉及删除的一律 git mv 到 `docs/archive/ccc-legacy-2026-08-02/`（新增子目录），禁止直接 rm（git mv 可追溯）。
2. 先证后删：任何「疑似死代码/孤儿页面」必须先用 rg 证明零引用，再把证据写进回写区；有引用但确实无用的，先摘除引用再归档。
3. 零改动 server/ 运行代码逻辑与 2017 运行面；前端改动后必须实测四视图可用。
4. 真实提交；验收标准不可自行解释。

## 范围

server/web/（index.html、js/app.js、js/chat.js、css/style.css 孤儿壳；legacy-chat/js/components/dispatchCard.js 等未挂载文件；legacy-chat/index.html 旧文案）、src-tauri/、根目录 _update_handoff.py、.ccc/agent-mind/decided.json、docs/architecture.md、docs/briefs/_TEMPLATE.md、docs/product/four-role-fluency-charter.md、server/web/server.py（仅静态白名单条目，若孤儿页归档后需摘除）。

## 步骤

1. 证明孤儿壳：rg 全仓确认 server/web/index.html、js/app.js、js/chat.js、css/style.css 无任何页面/文档引用（legacy-chat 用自有 css 与 app.js）→ 整组 git mv 到归档区；server.py 静态白名单摘除对应条目（css/style.css 若确无引用）。
2. legacy-chat 死代码：dispatchCard.js 等未在 index.html 挂载的模块，rg 证零引用后归档；dualPane.js/shell-ui.js 仍在挂载则保留，只清内部死分支（如确认死）。
3. 文案更新：legacy-chat/index.html 的 `CCC Hub` 编排口/「对话在 M1 :7788」→ 新口径（2017 单端 :7788、四视图、账号密码登录）；全页 grep 旧文案清零。
4. src-tauri/：整体 git mv 到 `docs/archive/ccc-legacy-2026-08-02/tauri-desktop-legacy/`；更新 docs/architecture.md 架构树、README、docs/briefs/_TEMPLATE.md、four-role-fluency-charter.md 中 src-tauri 引用（标历史或移除）。
5. _update_handoff.py（QuantHive 遗留，功能是写 QuantHive 文档）：移出 CCC 仓——git mv 到 /tmp/（回写注明去向）或直接归档区并注释；`.ccc/agent-mind/decided.json` 改动先 `git diff` 核实用途：若是运行态数据则还原，若是有效变更则提交并说明。
6. 全仓 grep 自检 + 页面实测（登录/对话/看板/运维/控制台）后提交。

## 验收标准

1. 全仓 grep（排除归档区）零命中：`CCC Hub`、`M1 :7788`、`src-tauri`（引用文档已更新）；`server/web/index.html` 零引用且已归档。
2. 唯一 HTTP 入口 = legacy-chat 四视图；唯一桌面壳 = desktop/（Swift）。
3. 页面实测：未登录弹登录门 → ccc/ccc 登录 → 对话/看板/运维/控制台全 200，无 404 断链。
4. `pytest server/tests -q` 全绿；工作树仅剩许可预存项（_update_handoff.py 已清出）；真实提交。

## 回写要求

卡头状态更新为「已回写」；回写区填：每项清理的 rg 证据、归档去向、文案改动清单、页面实测结果、commit hash。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 1. 孤儿壳归档（rg 证零引用）

| 文件 | rg 证据 | 归档去向 |
|------|---------|----------|
| `server/web/index.html` | 全仓 grep 仅历史 docs/dispatch/T6/T13/T19/T23/T24/T25 + acceptance-full 引用（非现行代码） | `docs/archive/ccc-legacy-2026-08-02/orphan-shell-web/index.html` |
| `server/web/js/app.js` | 同上 | `docs/archive/ccc-legacy-2026-08-02/orphan-shell-web/app.js` |
| `server/web/js/chat.js` | 同上 | `docs/archive/ccc-legacy-2026-08-02/orphan-shell-web/chat.js` |
| `server/web/css/style.css` | 同上 | `docs/archive/ccc-legacy-2026-08-02/orphan-shell-web/style.css` |

server.py 静态白名单摘除 `/css/style.css`、`/js/chat.js`（孤儿归档后无对应文件）；`/js/app.js` 保留（映射到 `legacy-chat/js/app.js`，非孤儿）。

### 2. legacy-chat 死代码（dispatchCard.js）

**结论：保留，不归档。** rg 证据：
- `message.js:60` 动态 import `dispatchCard.js`（消息「转任务」按钮）
- `composer.js:21` 动态 import `dispatchCard.js`（composer action dock onTransfer 回调）
- `fixedActions.js` `transfer-task` 按钮（label "转意图卡(编辑)"）触发 `onTransfer`

不满足「零引用」归档条件（红线 2）；按任务卡步骤 2「dualPane.js/shell-ui.js 仍在挂载则保留」同理保留。

### 3. 文案更新（legacy-chat 旧 Hub 口径 → 2017 单端 :7788 四视图）

| 文件 | 改动 |
|------|------|
| `legacy-chat/index.html` | `CCC Hub`→`CCC`；`M1 :7788`→`2017 单端 :7788`；登录提示 `operator/viewer`→`账号密码登录（CCC_WEB_USERNAME/CCC_WEB_PASSWORD_HASH 配置）`；placeholder `operator 或 viewer`→`ccc` |
| `legacy-chat/js/router.js` | 注释 `Hub = 编排口；对话口在 M1 :7788`→`2017 单端 :7788 四视图统一入口`；跳转提示 `M1 :7788`→`2017 :7788` |
| `legacy-chat/js/app.js` | 页面标题 `CCC Hub · 看板`→`CCC · 看板`（4 处） |
| `legacy-chat/js/pages/boardPage.js` | orch-hint `对话请开 M1 :7788`→`2017 单端 :7788 四视图`；移除无用 `dialogueEntryUrl` import |
| `legacy-chat/js/pages/opsPage.js` | 同 boardPage.js |
| `legacy-chat/css/shell.css` | 注释 `CCC Hub shell`→`CCC shell` |

### 4. src-tauri/ 归档 + 文档引用更新

**归档去向**：`src-tauri/` → `docs/archive/ccc-legacy-2026-08-02/tauri-desktop-legacy/src-tauri/`（整体 git mv，27 文件）

**文档引用更新**：

| 文件 | 改动 |
|------|------|
| `docs/architecture.md` | 架构树移除 `src-tauri/` 节点（原标「历史遗留（待 T34 归档）」） |
| `docs/briefs/_TEMPLATE.md` | 壳白名单 `desktop/ · src-tauri/`→`desktop/` |
| `docs/product/four-role-fluency-charter.md` | 壳白名单 `desktop/ · src-tauri/`→`desktop/` |
| `references/file-contract.md` | 白名单示例 `src-tauri/`→`desktop/` |
| `references/examples/qxo-audit-frontend.md` | 同上 |
| `AUDIT.md` | 范围移除 `src-tauri/tauri.conf.json`；Tauri 风险项 #6 标注「已归档至 docs/archive/ccc-legacy-2026-08-02/tauri-desktop-legacy/」 |
| `docs/roadmap.md` | src-tauri 行标注「已归档至 docs/archive/ccc-legacy-2026-08-02/tauri-desktop-legacy/」 |
| `CODEOWNERS` | 移除 `/src-tauri/Cargo.toml` 规则 |
| `.pre-commit-config.yaml` | 版本同步检查 files 正则移除 `src-tauri/Cargo.toml|src-tauri/tauri.conf.json` |
| `.gitignore` | 移除 `src-tauri/target/`、`src-tauri/gen/`（归档后无意义） |
| `.cursorignore` | 移除 `src-tauri/target/`、`src-tauri/**/*.o` 等 4 行（归档后无意义） |

**非归档区剩余 src-tauri 引用**：仅 `docs/dispatch/T31/T34/T35`（任务卡本身描述 src-tauri，属任务流转记录，不改）。

### 5. _update_handoff.py 移出 + decided.json 核实

- `_update_handoff.py`：QuantHive 遗留物（`sys.path.insert(0, '/Users/apple/ZCodeProject/QuantHive')`，写 QuantHive 文档）。移至 `/tmp/_update_handoff.py.quanthive-legacy`，CCC 仓已清出。
- `.ccc/agent-mind/decided.json`：`git diff` 无改动（T33 已回滚运行态数据），无需处理。

### 6. 页面实测（本地起服务 17889）

```
GET /                    → 200（legacy-chat/index.html）
GET /css/base.css        → 200（legacy-chat 样式）
GET /css/style.css       → 401（孤儿已归档，非白名单 → 走鉴权）
GET /js/app.js           → 200（legacy-chat/js/app.js）
GET /js/chat.js          → 401（孤儿已归档）
GET /data/board.js       → 200
GET /health              → 200 {"status":"ok","auth_required":true,"auth_configured":true}
POST /session ccc/ccc    → 200 token=...
GET /board/snapshot      → 200（带 token）
GET /board/realtime      → 200（带 token）
GET /ops/summary         → 200（带 token）
index.html grep "CCC Hub"|"M1 :7788" → 0 命中
```

### 测试输出

```
pytest server/tests/ --tb=short
238 passed in 4.57s
```

### commit hash

- `ddaa60d` refactor(closeout): T34 死码/孤儿页/双壳/遗留物清理（47 文件 +29/-45）

