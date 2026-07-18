# Plan: adv-ccc-auto-batch

来源: adversarial-2026-07-09.json

## 目标
批量修复 18 项自动可修问题:
  F2: ccc-notify.sh 拼接用户可控 MESSAGE 进 osascript -e
  F3: POST /api/tasks/move 客户端传 from 列无白名单校验 + update_in
  F4: CCC_WORKSPACES 环境变量未做绝对路径校验, 直接经 Path(...).expandu
  F5: /api/logs 端点把

## 文件
multiple

## 验收
- [ ] 修复完成
