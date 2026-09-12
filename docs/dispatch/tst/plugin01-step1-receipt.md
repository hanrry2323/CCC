# T-CCC-PLUGIN-01 序1 回执 · PI@195 跨机开发执行体落码（step1）

- 日期：2026-09-12 · 席位：2017 worktree `codex/plugin01-step1`
- 范围：wrapper 落仓 + executors.json 加槽 + card_gate 触发条件集合化 + 单测。不含实弹派发（序2 另单）。

## 1. 改动路径清单

| # | 路径 | 类型 |
|---|------|------|
| 1 | scripts/pi-remote-executor.sh | 新增（自 /tmp 版 scp 落仓，md5=218a5207827e42ae800b770ef1e97caa 两端一致，chmod +x，bash -n 通过） |
| 2 | server/config/executors.json.bak-before-plugin01-20260912 | 新增（改前备份；被 .gitignore `*.bak-*` 规则忽略，不入库） |
| 3 | server/config/executors.json | 修改（append PI@195 槽位，只加不改） |
| 4 | server/engine/card_gate.py | 修改（L207 触发条件单值等值→集合判断） |
| 5 | tests/test_card_gate_trigger.py | 新增（7 个用例） |
| 6 | docs/dispatch/tst/plugin01-step1-receipt.md | 新增（本回执） |

## 2. 改动点位置与代码摘录

### 2.1 server/config/executors.json（append 第 6 槽位）

追加于 `executors` 数组末尾（原 5 槽逐字段程序化比对不变，脚本输出 ORIGINAL5_UNCHANGED=YES）：

```json
{
  "角色": "开发执行体-195",
  "分类": "可后台 CLI",
  "当前绑定": "PI@195",
  "命令": "/Users/fan/program/CCC/scripts/pi-remote-executor.sh",
  "参数模板": "{card_path} {work_id} {worktree} {role} {biz_worktree}",
  "工作目录": "",
  "worktree_base": "",
  "备注": "跨机开发执行体（PI@195）：2017 engine 经 scripts/pi-remote-executor.sh 薄包装 SSH 到 195 跑 pi CLI（提案 v2 §一 A 线；Windows sh=cmd.exe，prompt 走 < 文件重定向，退出码由 ssh 透传）。卡面真值仍在 2017 本地仓（CAS+git 写锁），代码面在 195 worktree。",
  "worker_id": "PI@195",
  "注入提示": false
}
```

注：json.dump 整体重排导致备份与新文件 md5 不同属预期（原文件无尾换行、新文件有）；语义层面 version/description/原 5 槽逐字段相等已程序化验证。

### 2.2 server/engine/card_gate.py（L207-211，唯一代码改动点）

```python
    # T-CCC-PLUGIN-01 序1：触发条件由单值等值改集合判断——新增跨机执行体（PI@*）同样走
    # card_gate 五项校验，否则新卡头会静默跳过出卡门禁（提案 v2 必带项）。
    _VALIDATED_EXECUTORS = frozenset({"DSH", "PI@195"})
    if fields is None or fields.get("执行体") not in _VALIDATED_EXECUTORS:
        return GateResult(passed=True)  # 非受管执行体产卡不走新校验门
```

（任务书模板注释里「静末跳过」为笔误，按「静默跳过」落。）`validate_card` 本体、`GateResult` 导入、禁改清单文件均未触碰。「当前绑定」既有槽位未切换。

### 2.3 tests/test_card_gate_trigger.py（新增 7 用例）

1. `test_pi195_valid_card_passes_gate`：PI@195 合法卡 → enforce_card_gate 放行（改前会被静默跳过五项校验，现真实过五项）。
2. `test_pi195_valid_card_passes_five_checks_unit`：validate_card 层空问题清单。
3. `test_pi195_missing_impl_section_is_rejected`：缺「实现要求」→ passed=False/reason=card_gate/VOIDED+告警落盘。
4. `test_pi195_scope_path_missing_is_rejected`：范围路径不存在 → 拦截。
5. `test_dsh_legacy_behavior_unchanged`：DSH 合法放行/非法拦截判据不变。
6. `test_unmanaged_executor_cc195_still_passes`：未受管执行体 CC@195（卡内容故意非法）仍直接放行。
7. `test_registry_contains_pi195_slot`：注册表含 PI@195 绑定（配套一致性）。

## 3. executors.json 前后槽位数

- 改前：5（开发执行体/DSH、维护执行体、管理席、验收席、只读取证/审计执行体）
- 改后：6（新增 开发执行体-195/PI@195）
- 原 5 槽逐字段比对：不变（程序化验证，非肉眼）

## 4. pytest 结果（2017 worktree，python3.12 + pytest 9.1.1；仓内无 .venv，用系统解释器）

- 基线（改动前，`pytest server/tests/`）：**1 failed, 1498 passed, 2 skipped**，exit 1。
- 改后（`pytest server/tests/ tests/`）：**1 failed, 1516 passed, 2 skipped**，exit 1。
- 唯一失败 `server/tests/test_dsh_key_check.py::test_429_is_quota_and_ledger_alert`：**预存在失败**——stash 我的全部改动后干净树单跑该用例仍 failed（复现：`git stash push -- server/config/executors.json && python3 -m pytest server/tests/test_dsh_key_check.py::test_429_is_quota_and_ledger_alert`），与本单改动无关，未顺手修（超范围）。
- card_gate 相关专项（`pytest tests/test_card_gate_trigger.py server/tests/test_card_gate.py server/tests/test_engine_gates.py`）：**33 passed**（新 7 + 老 26），exit 0。**无回归**。

## 5. Windows 传参结论（5 条实测排除项，wrapper 形态依据）

1. 排除「ssh 里假定远端 sh=bash / 用 sh -c 语法」：195/252 Windows OpenSSH 的 `sh` 实为 cmd.exe，只能 `ssh 'cd /d <dir> && pi --model <M> -p < <promptfile>'` 形态。
2. 排除「远端 echo $? 捕获退出码」：cmd 下 `$?` 恒 0（假绿），退出码必须由 ssh 透传给 2017 engine。
3. 排除「PowerShell 直调 pi 的 .cmd」：参数会被拼成单串传给命令，语义错乱。
4. 排除「PowerShell -EncodedCommand 包装」：长路径会被截断。
5. 排除「prompt 内容走命令行参数拼接」：cmd 引号地狱+长度限制，prompt 一律 scp 上文件后 `< 文件` 重定向喂给 `pi -p`。

（wrapper 对 win 形态另有 PowerShell $LASTEXITCODE 捕获路径，PI_REMOTE_FORM=linux 走 @文件参数分支；本单目标机 195 为 win 形态。）

## 6. 未做事项（后续序单）

- CC@195 探针（卡头用未受管执行体的实弹探针）。
- PI@252 槽位（同型第二台，只加 executors.json 槽 + 目标机映射 env，wrapper 无需改）。
- 生产绑定切换：本次未把任何既有槽位「当前绑定」切到 PI@195，派发仍走 DSH；PI@195 生效需老板拍板后切换或按卡指定。
- 2017 生产仓（/Users/fan/program/CCC）合入：本单只落 worktree，合 main 走 code-review 流程。

---

## 关键数字（纯文本）

```text
wrapper_md5=218a5207827e42ae800b770ef1e97caa
executors_before=5
executors_after=6
card_gate_change_line=L207
new_test_cases=7
pytest_baseline="1 failed, 1498 passed, 2 skipped (exit 1)"
pytest_after="1 failed, 1516 passed, 2 skipped (exit 1)"
pytest_card_gate_scoped="33 passed (exit 0)"
pre_existing_failure=test_dsh_key_check.py::test_429_is_quota_and_ledger_alert
regressions=0
```
