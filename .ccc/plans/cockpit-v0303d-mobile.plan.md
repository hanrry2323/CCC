# Plan: cockpit-v0303d-mobile

## 目标
Cockpit & Chat 移动端适配

## 改动文件
`scripts/ccc-cockpit.py`, `scripts/ccc-chat-server.py`

## 具体任务

### Cockpit 端
- [ ] 机器芯片在手机屏幕换行显示（flex-wrap）
- [ ] 端口表格横滚支持
- [ ] 快速跳转按钮自适应宽度

### Chat 端
- [ ] safe-area-inset 适配刘海屏
- [ ] 输入框在键盘弹出时不被遮挡
- [ ] 消息列表在手机端占满宽度

### 验收
- [ ] iPhone Safari 打开页面布局正常
- [ ] 输入框不被键盘遮挡
- [ ] 所有内容无需横向缩放即可阅读
