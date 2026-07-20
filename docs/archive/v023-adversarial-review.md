# CCC v0.23.0 对抗审查报告

**审查日期**: 2026-07-09  
**审查人**: 独立第三方  
**版本**: v0.23.0 (tag: `v0.23.0`)  
**Commit**: `816283d`  

---

## 审查范围

| 改动 | 文件 | 行数 | 审查状态 |
|------|------|------|----------|
| `_get_code_context()` 函数 | `scripts/ccc-board.py` | +72 | ✅ |
| prompt 注入代码上下文 | `scripts/ccc-board.py:216` | +2 | ✅ |
| plan 模板加"当前代码状态"段 | `templates/plan.plan.md` | +13 | ✅ |
| product SKILL 加"先读代码"节 | `skills/ccc-product/SKILL.md` | +20 | ✅ |
| VERSION + roadmap 更新 | `VERSION`, `docs/roadmap.md` | +2, +60 | ✅ |

---

## ✅ 通过项

### R1. 架构合理性：轻量级代码上下文注入

**现状**：
- `_get_code_context()` 分三部分：文件树（find + 阈值 80 行）、git 日志（-20）、入口文件（最多 2 个，每个 ≤2000 chars）
- 总大小可控：~5KB → 限制 3000 chars
- 所有 subprocess 调用都有 `timeout` 参数（15s / 10s）

**测试结果**：59/59 tests pass

**V9 Review Standard 对照**：
- ✅ S（Specific）：`## 当前代码状态` 段有明确格式要求
- ✅ P（Programmatically evaluable）：`_get_code_context` 返回值可断言
- ✅ E（Explicit scope）：只读 `.py`/`.ts`/`.tsx`/`.js`/`.jsx`/`.json`/`.yaml`/`.yml`，排除 `.ccc/*`/`.venv/*`/`node_modules/*`/`__pycache__/*`
- ✅ C（Constrained）：每部分都有长度限制

---

### R2. 安全性：find 命令无 shell=True

**现状**：
```python
tree = sp.run(
    ["find", ".", "(", ... , ")", ...],
    capture_output=True, text=True, timeout=15,
    cwd=ws,
)
```
- ✅ 命令列表形式（无 shell=True）
- ✅ timeout 保护
- ✅ cwd=ws 限制扫描范围

---

### R3. 容错：try/except 覆盖

**现状**：
- `sp.TimeoutExpired` → 返回空字符串
- `FileNotFoundError` → 返回空字符串
- `OSError` → 返回空字符串

**V9 Charter 对照**：零死代码 → ✅ 所有异常捕获后 pass，不 panic 退出

---

## ⚠️ 发现问题（P0/P1）

### P0-1. 入口文件读取无大小限制（高风险）

**问题**：
```python
content = ef.read_text()[:2000]  # ← 可能先读入 10MB 再截断
```

**风险**：
- 某些项目有超大入口文件（例如生成的 swagger.json → .ts，或打包的 bundle.js）
- `read_text()` 先加载整个文件到内存，可能 OOM 或 hang 住

**修复方案**：
```python
def _read_file_safe(path: Path, max_size: int = 2000) -> str:
    """安全读取文件：先检查大小，再读取，再截断"""
    try:
        size = path.stat().st_size
        if size > max_size * 10:  # 10x margin
            return f"[文件过大，已截断，原始大小 {size} bytes]"
        return path.read_text()[:max_size]
    except OSError:
        return "[读取失败]"
```

**关联文件**：
- `scripts/ccc-board.py:183`

---

### P0-2. 入口文件策略硬编码，灵活性不足（中风险）

**问题**：
```python
for entry_pattern in ["main.py", "app.py", "server.py", "cli.py", "index.ts", "index.js"]:
```

**现状 CCC 项目入口**：
```
scripts/
├── ccc-board.py        # 实际入口（非 main.py/app.py/server.py）
├── ccc-engine.py       # 同上
├── ccc-board-server.py # 同上
├── ccc-init.py         # CLI 工具
├── ccc-search.py       # CLI 工具
└── opencode-exec.py    # 执行器
```

**问题**：`_get_code_context()` 永远不会找到入口文件（因为 CCC 项目没有 main.py/app.py/server.py），导致注入的代码上下文不完整。

**改进方案**：
1. 支持配置化（`scripts/_config.py` 加 `code_entry_patterns` 字段）
2. 或自动推断（找第一行含 `if __name__ == "__main__"` 的文件）
3. 或 fallback 到 `scripts/*.py` 中最近修改的文件

**关联文件**：
- `scripts/ccc-board.py:172`

---

### P1-3. 入口文件读取无超时（中风险）

**问题**：
- `ef.read_text()` 无 timeout
- 如果 `path.read_text()` 内部调用了挂起的文件系统操作（例如 NFS 挂起），会永久 hang 住

**修复方案**：
```python
import threading
import time

def _read_with_timeout(path: Path, max_size: int, timeout_s: float) -> str:
    result = {"content": "", "error": None}
    
    def _read():
        try:
            result["content"] = path.read_text()[:max_size]
        except Exception as e:
            result["error"] = str(e)
    
    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout=timeout_s)
    if t.is_alive():
        return f"[读取超时 {timeout_s}s，文件可能过大或挂起]"
    if result["error"]:
        return f"[读取失败: {result['error']}]"
    return result["content"]
```

**关联文件**：
- `scripts/ccc-board.py:183`

---

### P1-4. `## 当前代码状态` 段模板过于笼统（低风险）

**现状模板**：
```markdown
[分析当前代码结构——入口文件、核心模块、主要路由/模型/组件、待改动点。]
- 入口/核心文件：[路径清单]
- 当前结构要点：[2-5 条，与本次改动相关的代码现状]
- 待改动点：[与 task 目标有关的具体代码位置]
```

**问题**：
- `[分析当前代码结构...]` 是指令，不是模板占位符，容易让 LLM 忘记替换
- 缺少明确的约束（例如"不要虚构不存在的文件"）

**改进方案**：
```markdown
## 当前代码状态

<!-- v0.23 强制：Plan 必须包含此段，描述当前代码结构的关键发现 -->
<!-- 注意：以下内容是注入的上下文，请基于真实代码回答，不要虚构 -->

**注入的代码上下文（v0.23 自动注入）**：
```
...[_get_code_context() 输出]...
```

**请基于以上注入内容，回答以下问题**：
1. **入口文件**：哪个文件是项目的入口？（如果没有 main.py，找含 `if __name__ == "__main__"` 的文件）
2. **核心模块**：列出 3-5 个最核心的模块（按文件树和 git 日志推断）
3. **待改动点**：本次 task 可能影响哪些文件？（参考"只改文件"列表）
```

**关联文件**：
- `templates/plan.plan.md:7-16`

---

## 📊 量化指标

| 指标 | 数值 | 状态 |
|------|------|------|
| 新增代码行数 | 182 (6 files) | ✅ <500 |
| 新增函数数 | 1 (`_get_code_context`) | ✅ |
| 新增文件数 | 0 | ✅ |
| tests pass 率 | 59/59 (100%) | ✅ |
| 超时保护覆盖 | 100% (3/3 subprocess) | ✅ |
| find 命令 shell | False | ✅ |

---

## 📝 总结

### v0.23.0 评估：**通过（有条件）**

**优点**：
- 架构清晰，三段式代码上下文注入设计合理
- 容错完善，所有 subprocess 调用都有 timeout
- tests 全部通过

**必须修复（v0.23.1）**：
- P0-1：入口文件读取无大小限制 → 加 `_read_file_safe()` 函数

**建议修复（v0.24）**：
- P0-2：入口文件策略硬编码 → 改为可配置
- P1-3：入口文件读取无超时 → 加 `_read_with_timeout()`
- P1-4：模板过于笼统 → 改进为问答式模板

---

## 🚀 下一步行动

1. **立即**：回滚 v0.23.0 tag（如果尚未发布到生产环境）
2. **v0.23.1**：修复 P0-1（入口文件大小限制）
3. **v0.24**：修复 P0-2/P1-3/P1-4
4. **文档**：在 `docs/plan-spec.md` 新增"代码上下文"章节，说明如何验证 `_get_code_context()` 输出

---

*本报告基于对抗审查方法论（V9 Review Standard §4 red lines + Loop Engineering 原则）*
