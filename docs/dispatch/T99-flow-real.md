# 任务卡 T99-flow-real · 自动化流程真实任务验证：写运行手册（真实开发）

> 关联：阶段 3 流程验证（真实任务）· 执行体：Claude Code（2017）· 验收：Codex · 状态：待分派 · 日期：2026-08-04

## 目标

在 2017 开发 worktree（`/Users/fan/program/ccc-dev-ws`，分支 `codex/flow-real-001`）中完成一项真实开发：新增 `docs/runbooks/automation-flow.md`（CCC 自动化流程运行手册），提交并推送分支，验证「Codex 出卡 → Engine 自动派发 → 2017 执行体真实开发 → push → 回写」全链路。

## 工作目录与分支

- 工作目录：`/Users/fan/program/ccc-dev-ws`（git 身份已配置：CCC Dev）
- 分支：`codex/flow-real-001`（已基于 origin/main 创建，直接在此分支工作）

## 任务内容（写手册，内容要点必须覆盖）

新建 `docs/runbooks/automation-flow.md`，标题「CCC 自动化流程运行手册」，包含：

1. **流程链路**：Codex 出卡（docs/dispatch）→ push → 2017 pull → Engine 扫描派发 → 2017 执行体在 ccc-dev-ws 开发 → push 分支 → Codex 验收 → 合入 main → 2017 运行副本 pull + 服务重启（部署）。
2. **状态流转**：待分派 → 执行中 → 已回写 → 已关闭；失败打回附问题清单。
3. **关键命令**：Engine 手动触发 `$PYTHON_BIN -m server.engine.main --config server/config/config.env --once`；看板导出 `$PYTHON_BIN -m server.board.export --dispatch-dir docs/dispatch --output server/web/data/board.js`；服务重启 launchctl kickstart 三服务。
4. **测试任务先行纪律**：正式任务前必须跑 T9x-test 占位卡，跑通删除无残留。
5. **常见问题**：本地卡文件改动导致 pull 失败（先 checkout 丢弃测试卡改动）；执行体工作目录=ccc-dev-ws。

## 步骤

1. 在 ccc-dev-ws 创建 `docs/runbooks/automation-flow.md`（内容覆盖上述要点，格式用 Markdown，简洁准确）。
2. `git add docs/runbooks/automation-flow.md && git commit -m "docs(runbooks): 自动化流程运行手册"`。
3. `git push origin codex/flow-real-001`。
4. 输出确认（commit hash + push 结果）后结束。

## 红线

1. 只在 ccc-dev-ws 操作；**禁止改 2017 运行副本（/Users/fan/program/CCC）任何文件**。
2. 只新增该手册文件，不改其他代码；commit 只含该文件。
3. 如 push 失败（网络/凭证），如实报告错误并重试一次，不要伪造成功。

## 验收标准

1. 远程分支 `codex/flow-real-001` 存在且含真实 commit（手册文件，内容覆盖 5 要点）。
2. 卡头状态：待分派 → 执行中 → 已回写（Engine 自动派发）。
3. 看板可见；验收合入后测试卡删除无残留。

## 回写区

**执行体**：Claude Code（2017）· 日期：
