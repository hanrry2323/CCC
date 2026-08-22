# CCC 代码质量基线扫描（2026-08-22 · L1 机械指标）

> 范围：`server/` 平台核心（47 文件 / 23,919 行，剔除 tests/opencode-skills 第三方包）。
> 目的：回答「现在这套系统到底几分、烂在哪几个模块」，为「增量不可劣化」质量门禁建参照系。
> 工具：radon / mypy / 指纹法重复检测 / 测试断言·mock 密度。

## 一、核心结论

**质量画像：可运行但不可持续。** 结构复杂度集中、类型覆盖缺失、测试存在空转风险——这三者叠加，正是「表面跑通、实际质量无法评估」的量化证据。

## 二、指标明细

### 1. 圈复杂度（radon）· 结构复杂度热点
- 全 server 平均复杂度：**A（4.96）**（还行，但分布极不均）。
- **高复杂度函数（D/E/F 级）11 个，其中 8 个集中在 `server/web/server.py` 的 `_APIHandler`**：
  - `F` `_APIHandler.do_GET`（HTTP 总调度，巨型 if/elif 分发）
  - `E` `_APIHandler._handle_cards_search` / `_handle_cards_get`
  - `E` `FileBoardStore.list_work`（server/engine/store.py）
  - `D` `_handle_tasks_stream` / `_handle_loop_dsh_report` / `_handle_task_audit` / `_handle_task_transition` / `_handle_ops_failures`（全在 _APIHandler）
  - `F` `_Handler.do_GET`（chat_bridge.py）+ `D` `_Handler.do_POST`
- **结论：`server/web/server.py` 是上帝对象（~4600 行 HTTP 处理单体）**，是最大质量黑洞——改一处牵全局、极难测、机审也难审。

### 2. 类型覆盖（mypy）
- 全 server 非测试：**273 错误 / 25 文件**（共 47 源文件）。
- 仅 3 个文件配置 strict，且当前 mypy 配置还有 import 路径问题（task.py 无法完整检查）。
- **结论：类型门禁基本缺失**，类型相关 bug（None 解引用/错误类型参数）全靠运行时撞。

### 3. 重复代码（6 行指纹法）
- **266 组重复 6 行块（580 次出现）**——复制粘贴明显，改一处漏一处的风险高。

### 4. 测试质量（1165 测试 / 55 文件）
- 平均断言密度 ≈ **2.3 断言/测试**；**22 个测试文件断言/测试 < 2（空转风险）**。
- 高 mock 密度（mock/测试）：test_infra_resilience **10.5**、test_worktree_lifecycle **10.0**、test_writeback_gate **6.9**、test_brain **3.3**、test_observer **3.3**。
- **高风险组合（低断言 + 高 mock = 自说自话）**：
  - `test_engine_task.py`（断言/测试 **0.8**）
  - `test_engine_dispatch.py`（**1.3**）
  - `test_worker_routing.py`（**1.4**）
  - `test_kb_mcp.py` / `test_kb_service.py` / `test_kb_search.py`（1.6-1.9）
- **结论：部分模块测试是「高覆盖、全 mock、零拦截力」的空转测试**——这正解释了为什么 pytest 全绿却拦不住 xy056/057 这类假验证。

## 三、「烂在哪几个模块」答案

| 模块 | 问题 | 严重度 |
|------|------|--------|
| **server/web/server.py（_APIHandler）** | 上帝对象：8 个高复杂度函数、~4600 行、改一处牵全局 | 🔴 P0 |
| **类型覆盖整体缺失** | mypy 273 错误，3 文件 strict 只是摆设 | 🔴 P0 |
| **test_engine_task / dispatch / worker_routing** | 断言密度 <1.5，空转风险高 | 🟠 P1 |
| **kb_* 测试** | 断言密度 1.6-1.9 偏低 | 🟠 P1 |
| **全仓复制粘贴** | 266 组重复块 | 🟡 P2 |

## 四、作为门禁参照系

- **基线值（增量不可劣化参考）**：圈复杂度平均 A、mypy 273 errors、重复块 266、断言/测试 2.3。
- 建议门禁：新卡质量分 ≥ 存量基线（复杂度不劣化、mypy 新代码零错误、重复率不升、断言/测试 ≥ 2）。
- 趋势看板：按卡累计出分，看板可见。

## 五、复现命令

```
radon cc server/ -e "server/config/opencode-skills/*"        # 圈复杂度
python3 -m mypy server --exclude server/tests --follow-imports=skip | tail -1   # mypy 计数
（重复检测/断言密度：见本会话脚本，可脚本化）
```
