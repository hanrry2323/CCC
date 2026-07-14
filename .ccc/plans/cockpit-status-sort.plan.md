# Plan: cockpit-status-sort — 端口列表按健康状态排序

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

Cockpit 页面端口列表按 infrastructure.md 原文顺序（任意顺序）排列，dead 端口可能混在 alive 中间，运维时难一眼看到问题。

## 范围

- **目标**: 端口列表按 alive→warning→dead→unknown 排序，同状态内保持原序
- **只改文件**: `scripts/ccc-cockpit.py`

## 改动

1. render_html() 在端口渲染前排序：alive 排前 → warning → dead → unknown
2. 每组内维持 infrastructure.md 原始顺序
3. 每组添加视觉分隔线或浅色组标题 "Alive (8)" / "Dead (2)"
4. 页面统计数字同步更新

## 验收

- [排序] 页面端口列表按 alive→dead 顺序排列
- [分组] 每组有浅色标签 "Alive (8)"、"Dead (2)"
- [统计] 页面顶部统计与分组计数一致（alive+dead+unknown = total）
- [不变] 无端口列表时页面正常渲染（空列表不 crash）
