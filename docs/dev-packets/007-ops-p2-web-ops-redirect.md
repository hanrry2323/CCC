# DEV-PACKET: ops-p2-web-ops-redirect

> 合入权威 = Cursor。做完只提交到指定分支，不要 push main。  
> 先 `git checkout main && git pull`，再开分支。

## 1. 目标（用户可见）

网页 Hub 打开 `#/ops`（以及可选 `#/board`）时，不再渲染完整运维 SPA，而是一页人话：运维请用 **CCC Desktop**；可保留链到 `#/console` 作 SSH 兜底。

## 2. 分支与提交

- 分支：`draft/ops-p2-web-ops-redirect`
- 提交：`feat(hub-spa): redirect web #/ops to Desktop-first notice`
- 禁止 push main；禁止 `git add -A`

## 3. 白名单

- `scripts/chat_server/frontend/js/router.js`
- `scripts/chat_server/frontend/js/pages/opsPage.js`（或实际 ops 页入口文件）
- `scripts/chat_server/frontend/js/app.js`（仅当路由接线必须）
- 可选新建：`scripts/chat_server/frontend/js/pages/desktopRedirectPage.js`（短页）

## 4. 黑名单

- `desktop/**`
- `docs/product/loop-engineer-authority.md`
- `~/.ccc/**`
- 后端 Python（本包不删 `/api/ops`）

## 5. 现状锚点

- `router.js`：ROUTES 含 `ops`；`#/chat` 已跳对话口
- 档案：`docs/archive/deprecate-web-board-ops.md`（W3：ops 重定向提示）
- 产品主入口 = Desktop OpsView

## 6. 实现步骤

1. 为 `#/ops` 渲染简洁提示页（中文）：「运维已迁入 CCC Desktop（⌘3）。网页运维页停更。急需排查可开 #/console。」
2. `#/board` 可同样提示「看板请用 Desktop」，或本包只做 ops（优先只做 ops）
3. 不要删 `#/console`；不要删 Hub API
4. 静态检查：打开相关 js 无语法错误（可用 `node --check` 若适用）

## 7. 验收

```bash
node --check scripts/chat_server/frontend/js/router.js
rg -n "Desktop|ops|console" scripts/chat_server/frontend/js/router.js scripts/chat_server/frontend/js/pages/
```

## 8. 做完回报

```
BRANCH: draft/ops-p2-web-ops-redirect
FILES:
- …
TESTS:
- …
RESIDUAL:
- …
```
