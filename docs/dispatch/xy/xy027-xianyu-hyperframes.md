# 任务卡 xy027 · xianyu 视频里程碑推进：环境恢复+HyperFrames 高质量样片（OpenCode 执行）

> 关联：INT-122 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-09

## 目标

xianyu 视频项目：恢复 Mac2017 开发环境，产出 HyperFrames 高质量样片。

## 红线（先看）

1. 不碰已发布视频和成品素材
2. 不修改生产发布流程
3. 环境恢复用独立分支，不污染 main

## 范围

- M1 环境恢复：依赖安装、flash 模型接入（复用 CCC 6102）
- M2 高质量样片：HyperFrames 模板 + 渲染流水线

## 步骤

1. 环境检查：Mac2017 venv/依赖/GPU 状态
2. 依赖恢复：安装缺失包
3. flash 模型接入：复用 CCC 6102 出口
4. HyperFrames 模板调试
5. 样片渲染 + 质量评估
6. 验收：样片可播放、质量达标

## 验收标准

- 环境恢复后可运行现有脚本
- HyperFrames 样片渲染成功，质量 ≥ 参考样片
- 不引入新的环境依赖问题

## 回写要求

完成后更新本卡验收区，Engine 自动回写 INT-122。