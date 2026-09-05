# 任务卡 tst901 · smoke: card flow full-probe（DSH 执行）

> 关联：阶段 3 P1 · 执行体：DSH · 验收：DSH · 状态：作废（v2.0 清场：管线自检使命完成，防误认领） · 派发：engine · 项目：tst · 日期：2026-09-03 · 状态版本：1

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/tst/README.md`
- 项目业务仓：`/Users/fan/program/apps/ccc-tst/`（只读参考）
- 方案池：`docs/projects/tst/plans/`（关联方案见卡头「关联」）

## 目标

管线全链路冒烟（只读探针）：验证「出卡→执行通道→机审→回写」主链可用。本卡不产生业务改动，唯一产物是回写区里可复现的命令输出与卡标题复述。

## 实现要求

执行体必须先通读本卡全文，然后仅执行「步骤」节的命令，把输出如实填入回写区。

## 红线（先看）

1. 只读探针卡：禁止任何写操作（不碰业务仓文件、不改配置、不 commit/push 业务仓）。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

本卡只读，涉及以下真实存在的路径（仅读取，禁止改动）：

- `/Users/fan/program/apps/ccc-tst/README.md`（业务仓基准，存在）
- `/Users/fan/program/apps/ccc-tst/math_utils.py`（业务仓纯函数，存在）
- `/Users/fan/program/apps/ccc-tst/tests/test_math_utils.py`（业务仓单测，存在）
- `docs/dispatch/tst/tst901-smoke-full-probe.md`（本卡文件，存在）

## 步骤

1. **复述卡标题**：在回写区第 0 行写入卡标题全文「tst901 · smoke: card flow full-probe（DSH 执行）」——证明执行体已读到本卡内容。
2. 执行 3 条只读命令，把**原始输出**逐条记入回写区：
   - `git -C /Users/fan/program/CCC rev-parse --short HEAD`
   - `curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:7788/health`
   - `ls /Users/fan/program/apps/ccc-tst/math_utils.py`
3. 将卡头状态改为「已回写」，填维护区四问。

## 验收标准

1. 回写区第 0 行含卡标题复述「tst901 · smoke: card flow full-probe」（即执行体确实读到了带内容的卡）。
2. 回写区含 3 条命令的**原始输出**（git 短 hash / http 状态码 / 文件存在路径）。
3. 卡头状态为「已回写」，维护区四问逐项填写。

三条全满足 = 通过；任一不满足 = 打回。

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：
编译：
lint：
范围：false

## 回写要求

卡头状态更新为「已回写」；回写区填：卡标题复述、3 条命令原始输出、实现说明、push 证据（commit hash）。  
**回写同时必须完成维护区四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写；人审 diff 后听「合入批准」写+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：DSH · 日期：
0. 卡标题复述：
1. `git rev-parse --short HEAD` 输出：
2. `curl http://127.0.0.1:7788/health` 状态码：
3. `ls .../math_utils.py` 输出：

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是/否]（本卡为冒烟探针，无关联方案）
   - 说明：
2. **教训沉淀**：本卡是否产出可复用教训？[有/无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是/否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：
4. **线路图**：项目近况/下一步是否变化？[是/否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：

## 执行提示

- 项目：tst（CCC 管线自检专用（冒烟/E2E，无真实业务））
- 项目仓（只读参考）：/Users/fan/program/apps/ccc-tst（Mac2017）——禁止在主仓目录切换卡分支或直接开发
- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录
- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支
- 禁止：直推 main、写机审区/验收区、置已关闭
