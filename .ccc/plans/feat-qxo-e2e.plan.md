# feat-qxo-e2e

> 标题: qxo workspace 端到端测试

## 目标
跑 qxo workspace 全流程：create task → 6 角色流水线 → released。

## 文件白名单
- （无代码改动，只跑测试）

## 验收
1. qxo 项目有 1 个新 task 走完流水线
2. .ccc/board/released/ 出现新文件
