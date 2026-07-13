# Plan: cockpit-v0303a-design

## 目标
Cockpit UI 基础美化 — 设计系统规范化

## 改动文件
`scripts/ccc-cockpit.py`

## 具体任务

### 1. CSS 变量统一
当前 CSS 分散在 style 标签内，硬编码颜色多。改为：
- 统一定义 CSS 变量（--bg, --surface, --text, --accent, --border, --green, --red）
- 所有颜色引用走变量
- 圆角统一（--radius-sm: 6px, --radius-md: 10px, --radius-lg: 14px）

### 2. 布局间距对齐
- 卡片间间距统一 margin/padding
- 标题行与内容对齐
- 表格内 padding 统一

### 3. 快速跳转按钮美化
- 改为圆角胶囊按钮（border-radius: 20px）
- 悬停效果（轻微上移 + 阴影）

### 4. 端口状态圆点放大
- 从 8px → 10px
- 加轻微发光效果

### 验收
- [ ] 新 CSS 变量覆盖所有颜色
- [ ] 按钮有悬停效果
- [ ] 页面视觉更统一
