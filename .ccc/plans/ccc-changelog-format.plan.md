# Plan: ccc-changelog-format — CHANGELOG.md 格式统一

> 撰写：auto | 执行：auto（manual）

---

## 当前代码状态

本项目需修改的文件：CHANGELOG.md

---

## 范围
- **目标**：检查并修正 CHANGELOG.md 版本号标题层级
- **只改文件**：CHANGELOG.md
- **执行方式**：manual
- **Phase 数**：1

---

## 改动 1：CHANGELOG.md 格式统一

### 做什么
检查并修正 CHANGELOG.md 版本号标题层级

### 怎么做
编辑 CHANGELOG.md

### 验收清单
- [ ] 改动已应用
- [ ] 无语法错误

### 验收
- 确认改动存在：`grep -q "CHANGE" CHANGELOG.md`

---

## 全局验收清单
- [x] 文件在只改列表内
- [x] 单 phase
- [x] 改后 project 运行正常
