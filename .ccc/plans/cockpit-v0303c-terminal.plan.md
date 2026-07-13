# Plan: cockpit-v0303c-terminal

## 目标
Execute 模式终端体验优化

## 改动文件
`scripts/ccc-chat-server.py`

## 具体任务

### 1. 输出格式美化
- 执行结果用等宽字体（ui-monospace）显示
- stdout 和 stderr 分别用不同颜色
- 命令执行时间显示在输出块上方

### 2. 折叠卡片
- tool_use 事件显示为可折叠卡片
- 默认收起，点击展开
- 卡片内显示 tool 名称、输入参数、结果

### 3. 费用显示
- 每条执行结果末尾显示 token 用量和 $USD 费用
- 小号灰色文字

### 验收
- [ ] 执行结果用等宽字体显示
- [ ] tool_use 卡片可折叠展开
- [ ] 费用信息可见
