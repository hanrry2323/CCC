# 任务卡 tst905 · smoke: A1-A2 clean full-probe（DSH 执行）

> 关联：阶段 3 P1 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：tst · 日期：2026-09-03

## 基准文件（先看）

- 项目基准：`docs/projects/tst/README.md`。
- 业务仓 `/Users/fan/program/apps/ccc-tst/` 仅作只读参考，含 README.md、math_utils.py、tests/test_math_utils.py。
- 方案池：`docs/projects/tst/plans/`。

## 目标

验证 A1/A2 新链路：DSH 在业务 worktree 执行只读探针并产出 `.ccc-result.md`，wrapper 传输结果，引擎代写主仓卡并进入机审。

## 实现要求

执行体必须先通读本卡全文；只在引擎提供的 worktree 中执行步骤命令；禁止修改主仓卡，回写由引擎负责。

## 红线（先看）

1. 只读探针，不改业务仓文件、配置或主仓卡。
2. 不写 `## 机审区`、不改卡头状态、不执行手动 git push；结果交给 wrapper 和引擎。

## 范围

docs/dispatch/tst/tst905-smoke-clean-full-probe.md

## 步骤

1. 先把卡标题全文复述进 `.ccc-result.md` 的 `## 0. 卡标题复述` 段，证明已读卡。
2. 执行以下 3 条只读命令，并把原始 stdout/stderr 与退出码写进 `.ccc-result.md` 的探针/自测段：
   - `git -C /Users/fan/program/CCC rev-parse --short HEAD`
   - `curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://192.168.3.116:7788/health`
   - `ls /Users/fan/program/apps/ccc-tst/math_utils.py`
3. `.ccc-result.md` 必须包含 `## 0. 卡标题复述`、`## 1. 探针输出`、`## 2. 自测输出`、`## 3. 维护区四问`、`## 4. 变更证据` 五段；四问逐项回答并附说明。
4. 写完 `.ccc-result.md` 后停手；wrapper 传输结果，引擎代写主仓卡。

## 验收标准

1. `.ccc-result.md` 真产自执行体 worktree，且包含卡标题复述。
2. 结果文件包含 3 条命令的原始输出（git 短 hash、192.168.3.116:7788 health 状态码、math_utils.py 路径）。
3. 引擎代写主仓卡：回写区含标题复述/3 条输出，维护区四问完整，卡头为「已回写」并有引擎 commit。
4. 机审由 DSH auditor 真实执行，卡内落 `## 机审区` 与结论；判定不通过也必须保留原文。

四条全满足 = 通过；任一不满足 = 打回。

## 门禁

> 可选机械门禁
测试：
编译：
lint：
范围：false

## 回写要求

卡头状态由引擎改为「已回写」；引擎从 `.ccc-result.md` 填回写区与维护区四问。执行体不直接写主仓卡。
**回写同时必须完成维护区四问**（完成钩子，未填=机审打回+合入拒绝）。
机审由 DSH auditor 执行；人审 diff 后听「合入批准」写+已关闭。

## 人工批注

（无批注。）

## 回写区

（引擎从 `.ccc-result.md` 代写。）

## 维护区

> 完成钩子：引擎从 `.ccc-result.md` 代写，执行体不直接改本卡。

1. **方案同步**：[否]
   - 说明：本卡为独立管线冒烟，无关联方案。
2. **教训沉淀**：[无]
   - 说明：本卡仅验证既有链路，不新增业务教训。
3. **档案/README**：[否]
   - 说明：本卡不改变项目结构、技术栈或路径。
4. **线路图**：[否]
   - 说明：本卡不改变项目近况或下一步。

## 执行提示

- 项目：tst（CCC 管线自检专用，无真实业务）。
- 先 Read 任务卡全文；只在业务 worktree 内执行；主仓卡是只读指针。
- 完成后只写 worktree 根 `.ccc-result.md`，不要修改主仓卡，不要把 `.ccc-result.md` 加入业务仓 commit。
- 禁止直推 main、写机审区、置已关闭。
