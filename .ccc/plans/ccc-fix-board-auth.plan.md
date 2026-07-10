# Plan: ccc-fix-board-auth — board-server 加最低鉴权 + 绑定白名单

> 撰写：auto | 执行：manual
> 来源：adversarial-2026-07-09.json
> 严重度：HIGH

---

## 当前代码状态

对抗性审查 ADV-AUTH 发现 scripts/ccc-board-server.py 存在问题。

---

## 范围
- **目标**：[ADV-001] ccc-board-server.py 绑定 0.0.0.0 且 POST /api/tasks 无鉴权。加 QX_BOARD_TOKEN 环境变量校验，绑定地址改为 127.0.0.1 默认
- **只改文件**：scripts/ccc-board-server.py
- **执行方式**：manual
- **Phase 数**：1

---

## 改动 1：board-server 加最低鉴权 + 绑定白名单

### 做什么
[ADV-001] ccc-board-server.py 绑定 0.0.0.0 且 POST /api/tasks 无鉴权。加 QX_BOARD_TOKEN 环境变量校验，绑定地址改为 127.0.0.1 默认

### 怎么做
编辑 scripts/ccc-board-server.py

### 验收清单
- [ ] 问题修复
- [ ] 无语法错误
- [ ] 相关测试通过

---

## 全局验收清单
- [x] 单文件范围
- [x] 单 phase
