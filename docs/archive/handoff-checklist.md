# CCC Handoff Checklist

> **目的**：12 项验收项，判断 CCC 项目是否达到可移交状态。
> 每项标注：✅ 自动测试验证 / 🧪 人工 review 验证 / ❌ 未通过

---

## 1. 工程基础

| # | 检查项 | 验证方式 | 状态 |
|---|--------|----------|------|
| 1 | **README.md 完整**：含项目定位、安装流程、快速开始 | 🧪 人工 review | 🔲 |
| 2 | **CHANGELOG.md 完整**：v0.1→v1.0 版本链路，每个版本含 commit hash | 🧪 人工 review | 🔲 |
| 3 | **VERSION 文件**：当前版本号正确 | 🧪 检查 `cat VERSION` | 🔲 |
| 4 | **LICENSE**：开源许可证存在 | 🧪 人工 review | 🔲 |

## 2. 文档

| # | 检查项 | 验证方式 | 状态 |
|---|--------|----------|------|
| 5 | **docs/** 完整**：USAGE.md / CONTRIBUTING.md / GLOSSARY.md / TROUBLESHOOTING.md 各 ≥ 100 行 | 🧪 人工 review | 🔲 |
| 6 | **SKILL.md 完整**：能被 Trae/Cursor/VS Code 加载，含所有必要指令 | 🧪 人工 review | 🔲 |
| 7 | **references/** 完整**：cluster-protocol.md / red-lines.md / DESIGN-VALIDATION.md 各 ≥ 50 行 | 🧪 人工 review | 🔲 |

## 3. 测试

| # | 检查项 | 验证方式 | 状态 |
|---|--------|----------|------|
| 8 | **pytest tests/scripts/ -q 全通过** | ✅ `python3 -m pytest tests/scripts/ -q --tb=short` | 🔲 |
| 9 | **cluster 测试通过** | ✅ `python3 -m pytest tests/cluster/ -q --tb=short` | 🔲 |
| 10 | **cluster-bus 压测通过** | ✅ `python3 -m pytest tests/scripts/test_cluster_bus_benchmark.py -s` | 🔲 |

## 4. CI 与工具链

| # | 检查项 | 验证方式 | 状态 |
|---|--------|----------|------|
| 11 | **GitHub Actions CI 通过** | ✅ 查看 GitHub Actions 状态 | 🔲 |
| 12 | **pre-commit hooks 就绪** | ✅ `pre-commit run --all-files` 通过 | 🔲 |

---

## 总状态

| 类别 | 通过 | 总计 |
|------|------|------|
| 工程基础 | 0 | 4 |
| 文档 | 0 | 3 |
| 测试 | 0 | 3 |
| CI 与工具链 | 0 | 2 |
| **总计** | **0** | **12** |

---

## 使用方式

1. 逐项验证，将 🔲 改为 ✅（通过）或 ❌（不通过）
2. 不通过的项记录原因和修复方案
3. 全部 12 项通过后，CCC 可移交
