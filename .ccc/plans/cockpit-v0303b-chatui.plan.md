# Plan: cockpit-v0303b-chatui

## 目标
CCC Chat 页面 UI 美化 — 亮色主题统一

## 改动文件
`scripts/ccc-chat-server.py`

## 具体任务

### 1. CSS 变量统一
- 定义 CSS 变量（--bg, --surface, --text, --bubble-user, --bubble-assistant, --accent）
- 删除所有硬编码色值

### 2. 聊天气泡优化
- 用户气泡：右对齐，#007aff 背景，白色文字
- 助手气泡：左对齐，白色背景，#e5e5ea 边框
- 气泡圆角：18px（与设计规范一致）
- 消息间距：8px

### 3. 输入框美化
- 圆角 20px 胶囊输入框
- 发送按钮 #007aff 圆
- 输入时底部阴影

### 4. TabBar 样式
- 激活标签：#007aff 文字 + 底部指示条
- 非激活：#86868b
- 切换动画：平滑过渡

### 验收
- [ ] 聊天气泡样式符合 iOS 规范
- [ ] TabBar 切换有动画
- [ ] 输入框美观一致
