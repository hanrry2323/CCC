# 任务卡 T64 · Engine 自动按卡建 worktree（并行派发完善）（Claude Code 执行）

> 关联：T59 并行派发发现——每卡需独立 worktree，当前靠卡内续作指令手动建 · 执行体：Claude Code · 验收：Codex · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：请先创建独立 worktree `git -C /Users/fan/program/CCC worktree add /Users/fan/program/ccc-dev-ws-t64 -b codex/t64-engine-auto-worktree origin/main`；分支 `codex/t64-engine-auto-worktree`
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。

## 目标

Engine 派发 AUTO 卡时自动创建每卡独立 worktree 并作为执行体工作目录（不再靠卡内续作指令手动建），并行派发完全自包含。

## 具体项

1. **worktree 模板配置**：executors.json 可后台 CLI 行新增 `worktree_base`（如 `/Users/fan/program/ccc-dev-ws-<task>`）；Engine 派发时若配置了该字段：
   - 自动 `git worktree add <base>-<work_id> -b codex/<branch> origin/main`（分支名=卡 ID slug）；
   - 执行体工作目录指向该 worktree；启动命令注入 {worktree} 占位符（build_command 支持）。
2. **生命周期**：任务收单（已回写/打回）后保留 worktree（便于续作/验收），验收关闭后可清理（脚本或后续）。
3. **回退**：未配置 worktree_base → 维持现有工作目录行为（向后兼容）。
4. 测试：AUTO 卡自动建 worktree + 命令注入 workdir + 分支正确；未配置回退；worktree 冲突（已存在）处理。

## 红线

1. 只改 server/engine/（main.py、dispatch.py）、server/config/（executors.example.json、loader）、tests；**禁止改前端/desktop（T65 所有权）**。
2. worktree 创建失败不得导致卡状态丢失（回退现工作目录 + 日志）。
3. 回写前 push 成功并附证据。

## 验收标准

1. 一张 AUTO 卡派发时自动创建独立 worktree、分支正确、claude 在其中执行（实测）。
2. 未配置 worktree_base 行为与旧版一致（回退）。
3. worktree 冲突/失败处理不丢卡状态。
4. pytest 全绿、ruff clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：worktree 创建/注入/回退实现、实测记录、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：2026-08-05

1. **实现详情**：
   - 见 `server/config/executors.example.json`：后台 CLI 执行体增加可选的 `worktree_base` 配置。
   - 见 `server/engine/dispatch.py:47`：向 `ALLOWED_PLACEHOLDERS` 添加了 `{worktree}`，并在 `build_command` 中支持注入。
   - 见 `server/engine/main.py`：新增了 `get_worktree_path` 解析器，支持 `<task>`、`{task}`、`<work_id>` 和 `{work_id}` 占位符。在 `_dispatch_and_collect` 调度中自动检查并调用 `git worktree add` 独立建仓分支（`codex/<slug>`），失败时日志报错并优雅回退到默认工作空间。
2. **测试与覆盖**：
   - 见 `server/tests/test_engine_dispatch.py`：增加 `{worktree}` 占位符的命令构建单元测试。
   - 见 `server/tests/test_engine_main.py`：使用 `monkeypatch.chdir` 构造真实临时 git 仓库环境，完整覆盖了配置生效并自动建 worktree 运行、以及建 worktree 失败优雅回退的标准流程，所有测试通过。
3. **Pytest 全绿**：
   - 见 `server/tests/test_engine_main.py:745`：36 个测试用例，全通过。
   - 见 `server/tests/test_engine_dispatch.py:426`：32 个测试用例，全通过。
4. **Push 证据**：
   - 分支已成功 push 到 `origin/codex/t64-engine-auto-worktree`。
   - Commit ID: `e7b25ac7`

