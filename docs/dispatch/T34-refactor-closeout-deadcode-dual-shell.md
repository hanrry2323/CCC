# 任务卡 T34 · 重构收口：死代码/孤儿页面/双壳/遗留物清理（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§5 不越范围 / 提交卫生）
> 依据：Codex 2026-08-03 全新取证重评——孤儿看板壳 server/web/index.html 未被静态白名单挂载（"/" 走 legacy-chat）；legacy-chat 存在未挂载死代码（dispatchCard.js）与旧 Hub 文案（M1 :7788 / CCC Hub 编排口）；src-tauri 为 Tauri 旧 Cockpit 遗留、现行系统只用 desktop/（Swift）；根目录 _update_handoff.py 为 QuantHive 会话遗留物混入 CCC 仓
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03

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

**执行体**：Trae · 日期：

