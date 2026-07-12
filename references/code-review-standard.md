# 代码审查标准与流程 (v1.0)

> 基于 CCC 项目现有 7 角色系统和红线约束构建的系统化代码审查标准。

---

## 1. 审查范围与分类

### 1.1 按代码规模分类

| 类别 | 代码行数 | 审查强度 | LLM 必调 | Fallback 策略 |
|------|---------|---------|----------|---------------|
| **small** | ≤10 行 | 简化审查 | 可选 | py_compile 通过即可 |
| **medium** | 11-200 行 | 标准审查 | 必须 | quarantine + 人工介入 |
| **large** | >200 行 | 深度审查 | 必须 | quarantine + 人工介入 |

> **红线 X7 / R-12**: medium/large 类 LLM 不可达时禁止静默 verified。

### 1.2 按文件类型优先级

| 优先级 | 文件类型 | 审查重点 |
|--------|---------|---------|
| P0 | `scripts/*.py`, `scripts/*.sh` | 安全、可运行性、红线合规 |
| P1 | `tests/*.py` | 覆盖率、边界条件 |
| P2 | `templates/*.md` | 格式完整性 |
| P3 | 文档文件 | 正确性、可执行性 |

---

## 2. 审查维度与评分标准

### 2.1 五大审查维度

```
┌─────────────────────────────────────────────────────────────┐
│                    代码审查五大维度                            │
├───────────────┬───────────────┬───────────────┬─────────────┤
│   正确性      │    安全性     │   可维护性    │   性能      │
│  Correctness  │   Security    │Maintainability│ Performance │
├───────────────┴───────────────┴───────────────┴─────────────┤
│                           测试                                │
│                        Testing                                │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 各维度检查清单

#### 🔴 正确性 (Correctness) — 必须通过

- [ ] **功能完整**: 代码实现了 plan 中声明的所有功能
- [ ] **边界条件**: 循环边界、空输入、异常分支有处理
- [ ] **类型安全**: Python 有类型注解，关键路径无隐式 any
- [ ] **错误处理**: 关键操作有 try/except，异常信息有意义

#### 🔴 安全性 (Security) — 一票否决

- [ ] **无注入风险**: 无字符串拼接 SQL，无 eval()，无 shell=True
- [ ] **凭据安全**: 无硬编码密钥、token、密码
- [ ] **路径安全**: 无路径穿越漏洞 (`../` 未过滤)
- [ ] **输入验证**: 用户输入有校验

#### 🟡 可维护性 (Maintainability)

- [ ] **命名清晰**: 变量/函数/类名自解释
- [ ] **函数单一**: 单函数 < 50 行，只做一件事
- [ ] **无重复**: 相似代码 > 3 处应抽象
- [ ] **注释必要**: 复杂逻辑有解释，非显式自明

#### 🟡 性能 (Performance)

- [ ] **无 N+1**: 循环内无数据库/网络调用
- [ ] **资源释放**: 文件/连接/进程有 try/finally
- [ ] **算法合理**: 无明显低效实现

#### 🟡 测试 (Testing)

- [ ] **核心覆盖**: 关键路径有测试
- [ ] **边界覆盖**: 空值、异常、超限有测试用例

### 2.3 评分规则

| 等级 | 定义 | 阈值 |
|------|------|------|
| **PASS** | 所有 P0 项通过，无严重问题 | 100% P0 通过 |
| **CONDITIONAL_PASS** | P0 通过，有可接受的 P1/P2 问题 | P0 全绿 |
| **FAIL** | P0 有项未通过，或安全漏洞 | 任何 P0 失败 |

---

## 3. 审查流程

### 3.1 标准化流程图

```
┌─────────────┐
│   DEV 完成   │
│  提交代码   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│  计算规模   │────▶│  small?    │
│  (行数)    │     │  (≤10行)   │
└──────┬──────┘     └──────┬──────┘
       │                    │
       │Yes                 │No
       ▼                    ▼
┌─────────────┐     ┌─────────────┐
│  简化审查   │     │ 标准/深度   │
│ (py_compile)│     │   审查     │
└──────┬──────┘     │(LLM 必调)  │
       │            └──────┬──────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│  PASS?      │     │  LLM 可达?  │
└──────┬──────┘     └──────┬──────┘
       │                    │
  Yes  │               No  │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│   VERIFIED  │     │ quarantine  │
│  (进入下一列)│     │ +人工介入   │
└─────────────┘     └─────────────┘
```

### 3.2 详细步骤

#### Step 1: 代码获取

```bash
# 获取 diff
git diff HEAD~1

# 获取文件列表
git diff --name-only HEAD~1

# 统计行数
git diff --stat HEAD~1
```

#### Step 2: 规模判定

```python
def calculate_scale(diff: str) -> dict:
    """返回 {'category': 'small|medium|large', 'lines': N}"""
    # 统计新增+修改行数
    ...
```

#### Step 3: 执行审查

| 规模 | 审查方式 |
|------|---------|
| small | `py_compile` + 快速人工扫描 |
| medium/large | LLM 审查 + 人工复核 |

#### Step 4: 生成报告

审查报告输出到 `.ccc/reports/<task_id>.review.md`

#### Step 5: 产出 verdict

verdict 输出到 `.ccc/verdicts/<task_id>.verdict.md`

> **红线 11**: 禁止口头 PASS，必须写 verdict 文件

---

## 4. 报告模板

### 4.1 Review 报告结构

```markdown
# Code Review Report: <task_id>

## 基本信息

| 项目 | 值 |
|------|-----|
| Task ID | <tid> |
| 审查时间 | <datetime> |
| 审查者 | <reviewer> |
| 代码规模 | <small/medium/large> |
| 变更文件数 | N |

## 审查摘要

**Verdict**: PASS | CONDITIONAL_PASS | FAIL

**问题统计**:
- Critical: 0
- High: 0
- Medium: 0
- Low: 0

## 详细发现

### 🔴 Critical

| ID | 维度 | 文件:行号 | 描述 | 修复建议 |
|----|------|----------|------|---------|
| C-001 | Security | script/x.py:42 | SQL 注入风险 | 使用参数化查询 |

...

## 红线检查

- [ ] R-08: 日志使用 logger（无 print）
- [ ] R-09: GET 路径有认证
- [ ] X2: 进程正确释放
- ...

## 审查证据

```
# LLM 审查 prompt 摘要
...

# 关键 diff 片段
...
```

> **审查者签名**: <reviewer_id>
> **时间戳**: <iso8601>
```

### 4.2 Verdict 结构

```markdown
# Verdict: <task_id>

## 结论

**VERDICT**: PASS | FAIL | CONDITIONAL_PASS

## 验证项 (≥3 probes)

| # | 验证项 | 结果 | 证据 |
|---|--------|------|------|
| 1 | py_compile 通过 | ✅ | stdout: ... |
| 2 | 红线 R-08 合规 | ✅ | 无 print 调用 |
| 3 | 功能与 plan 一致 | ✅ | 实现了 X, Y, Z |

## 发现摘要

- Critical: 0
- High: 0
- Medium: 1
- Low: 2

## 下一步

[CONDITIONAL_PASS 时列出需要修复的问题]
```

---

## 5. 自动化工具

### 5.1 现有工具

| 工具 | 用途 | 位置 |
|------|------|------|
| `_review_validator.py` | 审查报告 JSON 校验 | `scripts/` |
| `py_compile` | Python 语法检查 | 系统自带 |
| `ruff` | Lint 检查 | 需安装 |
| `mypy` | 类型检查 | 需安装 |

### 5.2 建议配置

```bash
# 安装审查依赖
pip install ruff mypy

# 快速本地审查命令
alias code-review="ruff check . && mypy scripts/ && python -m py_compile"
```

---

## 6. 红线检查清单

### 6.1 必检红线

| 红线编号 | 检查项 | 检查方式 |
|----------|--------|---------|
| R-04 | reviewer 互斥锁 | 检查 lock 文件创建/释放 |
| R-07 | phases.json 原子写 | 检查 fcntl.flock 使用 |
| R-08 | 日志统一 logger | grep 无 `print` 冒充日志 |
| R-09 | 认证 GET 路径 | 检查 `_verify_auth()` 调用 |
| X1 | OpenCode ≤3 并发 | 检查 Semaphore(3) |
| X2 | 进程必杀 | 检查 try/finally 杀进程 |
| X7/R-12 | medium/large LLM 审查 | 检查 fallback 行为 |

### 6.2 自动检查脚本

```bash
#!/bin/bash
# check-red-lines.sh — 快速红线检查

echo "=== R-08: 日志检查 ==="
grep -rn "^[[:space:]]*print(" scripts/*.py | grep -v "logger\|log\." || echo "✅ 无 print 日志"

echo "=== X2: 进程杀检查 ==="
grep -n "finally:" scripts/*.py | head -5

echo "=== R-09: 认证检查 ==="
grep -n "_verify_auth" scripts/ccc-board-server.py
```

---

## 7. 审查频率与角色

### 7.1 CCC 看板角色职责

| 角色 | 触发条件 | 审查内容 |
|------|---------|---------|
| **reviewer** | dev 完成后自动触发 | 代码审查 + 红线检查 |
| **tester** | dev 完成后自动触发 | pytest + plan 逐条验收 |
| **ops** | 空闲时运行 | 健康检查 + 告警 |

### 7.2 审查时机

- **每次代码提交**: 自动触发 reviewer
- **每日审计**: ops 扫描全部项目
- **发布前**: regress 角色回归测试

---

## 8. 质量门禁

### 8.1 进入下一阶段的条件

| 当前阶段 | 下一阶段 | 门禁条件 |
|---------|---------|---------|
| in_progress | testing | dev 提交 + report.md 产出 |
| testing | verified | reviewer PASS + tester PASS |
| verified | released | kb 完成 tag + push |

### 8.2 阻塞条件

- ❌ reviewer verdict = FAIL → 阻塞进入 verified
- ❌ 红线违反 → 整个任务回退
- ❌ 无 verdict 文件 → 红线 11 违反

---

## 附录: 快速参考

### 常用命令

```bash
# 本地快速审查
ruff check scripts/
mypy scripts/
python -m py_compile scripts/*.py

# 获取变更
git diff HEAD~1 --stat
git diff HEAD~1

# 触发 reviewer (CCC Engine 自动)
# 手动: ccc-board.py reviewer_role
```

### 审查输出路径

```
.ccc/
├── reports/<task_id>.review.md   # 审查报告
├── verdicts/<task_id>.verdict.md # 验收结论
└── review-locks/<task_id>.lock   # 互斥锁(自动)
```

---

> **版本**: v1.0  
> **维护者**: 代码审查专家  
> **更新**: 基于 CCC 红线系统和 7 角色架构构建
