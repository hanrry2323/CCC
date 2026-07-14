# Plan: cockpit-dead-counter-badge — 页面标题 dead 端口数量角标

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

Cockpit 页面标题固定显示 "CCC Cockpit"，浏览器标签页无法反映服务健康状态。用户需切换到 Cockpit 标签页才能看到 dead 端口。

## 范围

- **目标**: 页面标题实时反映 dead 端口数量，如 "CCC Cockpit (2)"
- **只改文件**: `scripts/ccc-cockpit.py`

## 改动

1. render_html() 的 JS `fetchAlive()` 回调中更新 `document.title`
2. dead=0 时显示 "CCC Cockpit"，dead>0 时显示 "CCC Cockpit (N)"
3. favicon 用 canvas 动态生成红/绿圆点（dead>0 红色，dead=0 绿色）
4. 轮询 30s 时同步更新 title + favicon

## 验收

- [title] 有 dead 端口时页面标题变为 "CCC Cockpit (2)"
- [title 还原] 端口恢复 alive 后 title 回到 "CCC Cockpit"
- [favicon] 浏览器标签页 favicon 为绿色（alive）或红色（dead>0）
- [边界] 端口不返回 alive/dead（unknown 状态）不会误标红
