# Plan: ccc-fix-tester-shell-true — tester_role shell=True 改为 shell=False

> 撰写：auto | 执行：manual
> 来源：adversarial-2026-07-09.json
> 严重度：HIGH

---

## 当前代码状态

对抗性审查 ADV-TRUE 发现 scripts/ccc-board.py:971 存在问题。

---

## 范围
- **目标**：[ADV-010] ccc-board.py:971 sp.run(cmd, shell=True) 若 plan.md 被注入含 ; 或 $() 的验收命令可 RCE。改为 shell=False + shlex.split
- **只改文件**：scripts/ccc-board.py
- **执行方式**：manual
- **Phase 数**：1

---

## 改动 1：tester_role shell=True 改为 shell=False

### 做什么
[ADV-010] ccc-board.py:971 sp.run(cmd, shell=True) 若 plan.md 被注入含 ; 或 $() 的验收命令可 RCE。改为 shell=False + shlex.split

### 怎么做
编辑 scripts/ccc-board.py

### 验收清单
- [ ] 问题修复
- [ ] 无语法错误
- [ ] 相关测试通过

---

## 全局验收清单
- [x] 单文件范围
- [x] 单 phase
