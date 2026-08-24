# 任务卡 ccc072 · 卡头校验器语义修复——已关闭卡豁免「批准」章（DSH 执行）

> 关联：无方案（2026-08-24 债务清偿 · 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

消除平台组件自相矛盾：approve-merge 人审节点③在每张卡关闭时盖「> 批准：老板合入批准」于卡头（close_card 有意设计），而 server/board/validate.py L343-348 无条件将「批准」列为违禁卡头字段 → 每张新合并卡瞬间毒化所属项目出卡校验通道（tst004/ccc068/xy059 实证）。修复=对「已关闭」卡豁免「批准」键检查；未关闭卡仍严格报错；其余违禁键不变。

## 实现

白名单：server/board/validate.py、server/tests/test_validator_closed_card_approval.py（新增）。

1. validate.py：FORBIDDEN_HEADER_KEYS 循环前取卡头状态，base_state 为「已关闭」时跳过「批准」键检查（「审批/review/approval」仍全态报错）；注释引用人审节点③设计（scripts/approve-merge.sh close_card）与本卡。
2. 新增测试两张 tmp 卡夹具（唯一差异=状态 已关闭 vs 待分派，均含该行）：断言前者零 issue、后者含对应 issue。
## 红线（先看）

1. 白名单外零触碰；禁直推 main；禁 git add -A。
2. 仅按实现节条件豁免，禁止扩大豁免范围。
3. 禁写机审区/验收区/置已关闭。

## 步骤

1. Read 本卡全文与相关代码/文件现状。
2. 按实现节修改；自测运行下方门禁命令，退出码必须=0。
3. commit+push 到本分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。

## 验收标准

1. 门禁命令真实退出码=0（wrapper 证据日志为准）。
2. 白名单外零触碰。
3. 卡头=已回写；维护区四问非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/ccc072 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_validator_closed_card_approval.py -q

## 回写区

（执行体回写）

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：[否]。债务清偿直派卡无关联方案。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：[无]。机制性教训已在同期 notes 记录。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：[否]。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：[否]。
