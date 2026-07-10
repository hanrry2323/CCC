# Plan: ccc-docstring-sweep — scripts/ 模块级 docstring

> 撰写：auto | 执行：auto（manual）

---

## 当前代码状态

本项目需修改的文件：scripts/ccc-engine.py scripts/_board_store.py scripts/_config.py scripts/ccc-notify.sh scripts/opencode-exec.py

---

## 范围
- **目标**：给 5 个脚本补模块级 docstring
- **只改文件**：scripts/ccc-engine.py scripts/_board_store.py scripts/_config.py scripts/ccc-notify.sh scripts/opencode-exec.py
- **执行方式**：manual
- **Phase 数**：1

---

## 改动 1：scripts/ 模块级 docstring

### 做什么
给 5 个脚本补模块级 docstring

### 怎么做
编辑 scripts/ccc-engine.py scripts/_board_store.py scripts/_config.py scripts/ccc-notify.sh scripts/opencode-exec.py

### 验收清单
- [ ] 改动已应用
- [ ] 无语法错误

### 验收
- 确认改动存在：`grep -q "CHANGE" scripts/ccc-engine.py scripts/_board_store.py scripts/_config.py scripts/ccc-notify.sh scripts/opencode-exec.py`

---

## 全局验收清单
- [x] 文件在只改列表内
- [x] 单 phase
- [x] 改后 project 运行正常
