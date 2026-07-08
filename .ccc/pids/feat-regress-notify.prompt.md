# CCC 执行任务: feat-regress-notify

## Plan

# feat-regress-notify

> 标题: regress 发现回归时发桌面通知

## 目标
regress 发现回归后，除了建 bug 到 backlog，还调 scripts/ccc-notify.sh 发 macOS 通知。

## 文件白名单
- scripts/ccc-board.py（regress_role 增强）

## 验收
regress_role() 创建 bug 前调 notify


## 完成定义
1. 实现所有需求
2. 跑对应的测试（如有）
3. 提交一个 commit（message 以 feat-regress-notify 开头）
4. 确认代码无语法错误
5. 不超出 plan 文件白名单
