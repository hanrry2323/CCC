# Plan: cockpit-search-filter — 实时搜索过滤端口

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

Cockpit 端口列表全部展示，项目数超过 20+ 时查找特定端口需 Cmd+F 浏览器搜索。

## 范围

- **目标**: 添加实时搜索输入框，按端口名/项目名/地址过滤列表
- **只改文件**: `scripts/ccc-cockpit.py`（内嵌 HTML/JS/CSS）

## 改动

1. render_html() 顶部添加 `<input id="search" type="text" placeholder="搜索端口/项目/地址...">`
2. JS 监听 `input` 事件：`.toLowerCase.includes(query)` 过滤端口行
3. 无匹配时显示 "未匹配任何端口" 灰色占位
4. 搜索框有 `x` 清除按钮
5. 使用 input 事件（非 keyup），粘贴场景也触发

## 验收

- [搜索] 输入 "pg" 时仅显示匹配 "pg" 或 "PG" 的端口行
- [清除] 点击清除按钮后恢复完整列表
- [无匹配] 输入不存在的关键词时显示 "未匹配任何端口"
- [性能] 100 行以内过滤无卡顿（无 debounce 需求）
