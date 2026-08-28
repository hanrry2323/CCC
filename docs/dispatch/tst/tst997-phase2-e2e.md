# 任务卡 tst997 · Phase2 后半段自动闭环 E2E
> 关联：Phase1 E2E 测试卡（外脑直发·不走出卡流程） · 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：tst · 日期：2026-08-28

## 目标
验证 已回写 → CC 审核 → 合入 → 提交 → 部署 → 探活 → 已关闭 全自动闭环。

## 实现
本卡为平台验证卡：唯一产物为该卡文件本身（状态=已回写）。

## 红线
无业务代码改动；不碰风控配置。

## 范围
仅 docs/dispatch/tst/tst997-phase2-e2e.md。

## 步骤
1. 卡落盘（状态=已回写）+ 分支 codex/tst997-phase2-e2e push origin。
2. phase2 消费 → CC 审核 → 合入 main → 门禁 → 关闭 → 部署 → 探活。

## 验收标准
- 卡最终 board 状态 = 已关闭。
- 合入提交在 main 上可见；web :7788 /health 响应正常。

## 门禁
- 测试：python3 -c "print('phase2-gate-ok')"

## 维护区
- 维护说明：平台验证卡，随 Phase1 交付报告关闭。
