# 任务卡 ccc090 · new-card.sh 出卡原子化——落盘即提交即推送（DSH 执行）

> 关联：R1-R4 出卡吃单窗三次实锤 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

出卡工具内建原子性：new-card.sh 在写卡成功后**同一进程链内自动** `git add <卡> && git commit`（消息前缀 docs(card):）并尝试 `git push origin main`（任务卡 push 属出卡 SOP），任一步失败即非零退出并保留现场文件。彻底消灭「落盘未提交被 _force_align_dispatch 按 untracked 清除」的吃单窗（R3/R4 共四次实锤）。

## 红线

- 白名单：scripts/new-card.sh。
- --dispatch-dir 指向临时目录（测试形态）时跳过 git 步骤，保持现有测试兼容。
- push 失败不回滚本地 commit（卡已在本地受保护），输出显式警告与手动补推指引。

## 步骤

1. 写卡+validate 通过后追加原子提交段（git add 单文件→commit→push，逐段捕获 rc 并输出明确日志）。
2. 自测：真实出一张演练卡验证全链；tmp 目录模式验证跳过逻辑。

## 验收标准

- [ ] 真实出卡后 git log 立即可见该卡 commit 且已推送
- [ ] tmp 模式零 git 副作用
- [ ] bash -n 通过

## 回写要求

- 回写区附演练卡号与 push 输出；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）
