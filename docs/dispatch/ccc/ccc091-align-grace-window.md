# 任务卡 ccc091 · 引擎对齐宽限窗——未跟踪新卡不再静默清除（DSH 执行）

> 关联：R1-R4 吃单窗纵深防御 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

server/git_sync.py `_force_align_dispatch` 对 dispatch 子目录内 **mtime 距今 < GRACE_SECONDS（默认 300s，env CCC_ALIGN_GRACE_SECONDS 可调）的未跟踪 .md 新卡**不做清除，改为 logger.warning 告警一次（同文件去重）；超宽限仍存在才按原逻辑移除。纵深防御：即使出卡方忘记提交，卡也不会无声死亡。

## 红线

- 白名单：server/git_sync.py、server/tests/。
- 不改变已跟踪文件的对齐语义；不动 ff-only 主流程。
- 告警须含文件名与「疑似出卡未提交」提示。

## 步骤

1. _force_align_dispatch 移除未跟踪文件前按 mtime 过滤，命中宽限窗的记 warning 集合计数返回。
2. 自测：单测构造 untracked 新卡（mtime 新鲜）断言不被移除；伪造旧 mtime 断言被移除。

## 验收标准

- [ ] 两条单测绿
- [ ] 生产语义不变（ff-only 主流程零改动）

## 回写要求

- 回写区附单测输出与 diff 要旨；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）
