# Plan: ccc-fix-flock-fallback — _HAS_FLOCK=False 时写操作加文件锁降级防御

> 撰写：auto | 执行：manual
> 来源：adversarial-2026-07-09.json
> 严重度：HIGH

---

## 当前代码状态

对抗性审查 ADV-FALLBACK 发现 scripts/_board_store.py:69-75 存在问题。

---

## 范围
- **目标**：[ADV-006] _board_store.py 在 Linux/macOS 以外平台 _HAS_FLOCK=False 时所有写操作零并发保护。加独占文件创建原子锁（OS-level fallback）
- **只改文件**：scripts/_board_store.py
- **执行方式**：manual
- **Phase 数**：1

---

## 改动 1：_HAS_FLOCK=False 时写操作加文件锁降级防御

### 做什么
[ADV-006] _board_store.py 在 Linux/macOS 以外平台 _HAS_FLOCK=False 时所有写操作零并发保护。加独占文件创建原子锁（OS-level fallback）

### 怎么做
编辑 scripts/_board_store.py

### 验收清单
- [ ] 问题修复
- [ ] 无语法错误
- [ ] 相关测试通过

---

## 全局验收清单
- [x] 单文件范围
- [x] 单 phase
