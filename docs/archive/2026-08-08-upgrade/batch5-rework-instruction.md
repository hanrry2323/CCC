# 批次 5 返工指令 · 删除 pytest 豁免（回写凭证校验纯净化）

> 验收判定：P3/状态机校验器/熔断统计通过；`check_writeback_credentials` 的测试豁免为反模式 → 返工
> 范围极小：只改校验函数语义 + 测试适配，不动已通过的 P3/状态机/熔断逻辑

## 问题（先看懂）

`server/engine/main.py` `check_writeback_credentials` 现实现：

```python
if "pytest" in sys.modules or "unittest" in sys.modules:
    if not any(x in stem for x in ("xy101", "xy105", "xy106", "xy107")):
        return True, ""
```

问题：
1. **生产代码藏测试分支**（反模式，测试豁免列表会腐烂）
2. 空回写校验在测试环境只对 4 个 ID 生效 → 校验行为在测试中不可证明
3. 豁免掩盖了真实语义缺陷：现实现「未找到 ## 回写区 → 拦截」，而存量测试卡（构造 md 无回写区节）全部会被拦截

## 根因与干净语义

真实业务卡八节结构**必含 `## 回写区`**（new-card.sh 模板）。真实空回写卡（mx023/mx025 卫生任务实证）形态是「**有回写区节但内容空白**」。存量测试卡形态是「**无回写区节**」。

干净语义（三态）：
- **无 `## 回写区` 节** → 放行（不适用；历史构造卡）
- **有节但内容空白** → 拦截「空回写卡（回写区无凭证内容），禁止空提交收单」
- **有节有内容但缺凭证字段**（`分支=codex/<slug>` / `commit=<sha>`）→ 拦截

## 返工任务

### 任务 1：删豁免 + 三态语义

改 `check_writeback_credentials`：
1. **删除** pytest/unittest 豁免分支
2. `if not in_writeback: return True, ""`（无节放行，加注释说明真实空回写卡=有节空白）
3. 保留：有节空白 → 拦截；凭证字段缺失 → 拦截
4. 函数 docstring 更新为三态语义

### 任务 2：测试适配

`server/tests/test_writeback_gate.py`：
1. 现有 `test_check_writeback_credentials` 若断言「未找到回写区 → 拦截」→ 改为「→ 放行」
2. **补用例**：无回写区节 → 放行；有节空白 → 拦截；缺 `分支=` → 拦截；缺 `commit=` → 拦截；齐全 → 通过
3. 其余测试（P3/熔断统计）不动

### 红线

1. 只动 `check_writeback_credentials` + test_writeback_gate.py；**不动** P3 空提交判定/validate.py 状态机校验器/机械门禁/批次 1-4 逻辑
2. 禁 `git add -A`；禁碰 2017/卡文件内容

## 验证

1. `pytest server/tests/test_writeback_gate.py -v` 全绿
2. `pytest server/tests/` 全绿（t53 存量 3 失败除外）——**证明删豁免后无回归**
3. `grep -n 'pytest' server/engine/main.py` 无 sys.modules 豁免残留
4. `git status` 干净

## 交付

1. 改动文件 + diff 摘要
2. 单测输出
3. push commit hash
