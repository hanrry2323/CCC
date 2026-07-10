# Plan: ccc-gitignore-update — .gitignore 加运行时数据

> 撰写：auto | 执行：auto（manual）

---

## 当前代码状态

本项目需修改的文件：.gitignore

---

## 范围
- **目标**：加 .ccc/board/events/ 和 .ccc/pids/
- **只改文件**：.gitignore
- **执行方式**：manual
- **Phase 数**：1

---

## 改动 1：.gitignore 加运行时数据

### 做什么
加 .ccc/board/events/ 和 .ccc/pids/

### 怎么做
编辑 .gitignore

### 验收清单
- [ ] 改动已应用
- [ ] 无语法错误

### 验收
- 确认改动存在：`grep -q "CHANGE" .gitignore`

---

## 全局验收清单
- [x] 文件在只改列表内
- [x] 单 phase
- [x] 改后 project 运行正常
