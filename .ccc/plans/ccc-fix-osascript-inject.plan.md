# Plan: ccc-fix-osascript-inject — osascript notify 参数引用加固

> 撰写：auto | 执行：manual
> 来源：adversarial-2026-07-09.json
> 严重度：MEDIUM

---

## 当前代码状态

对抗性审查 ADV-INJECT 发现 scripts/ccc-notify.sh:56-60 存在问题。

---

## 范围
- **目标**：[ADV-002] ccc-notify.sh:56,60 用双引号拼接 $MESSAGE/$TITLE 到 osascript -e。改用 printf %s 或 heredoc 传参，阻止 AppleScript 注入
- **只改文件**：scripts/ccc-notify.sh
- **执行方式**：manual
- **Phase 数**：1

---

## 改动 1：osascript notify 参数引用加固

### 做什么
[ADV-002] ccc-notify.sh:56,60 用双引号拼接 $MESSAGE/$TITLE 到 osascript -e。改用 printf %s 或 heredoc 传参，阻止 AppleScript 注入

### 怎么做
编辑 scripts/ccc-notify.sh

### 验收清单
- [ ] 问题修复
- [ ] 无语法错误
- [ ] 相关测试通过

---

## 全局验收清单
- [x] 单文件范围
- [x] 单 phase
