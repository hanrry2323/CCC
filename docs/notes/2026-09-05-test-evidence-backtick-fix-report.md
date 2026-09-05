# test-evidence 反引号提取修复报告

日期：2026-09-05
状态：已完成

## 1. 根因与范围

- 根因：`docs/dispatch/xy/xy060-content-library-api.md` 的门禁行使用行内代码包裹测试命令，并在闭合反引号后带中文括号说明；旧实现使用 `strip(chr(96))`，只能剥字符串两端的反引号，说明文本前的闭合反引号残留到 `eval`，造成 `unexpected EOF`，将真实已通过的业务自测误判为测试证据失败。
- 修复范围：仅修改 `scripts/test-evidence.sh` 的测试命令提取逻辑，并新增 CCC 主仓回归测试；未修改 xy060 业务代码、任务卡正文或卡状态。

## 2. 实现

- Python 解析器识别一个 Markdown 行内代码 span，截取合法闭合反引号之前的命令；闭合 span 后的中文/英文括号说明不会进入 `TEST_CMD`。
- 未被行内代码包裹的命令保持原文，因此合法 shell 命令内部的反引号不被粗暴删除。
- 保留全角冒号优先解析，pytest 节点 ID 中的 `::` 不会被腰斩。
- `eval` 仍按原语义执行；证据头打印的 `cmd` 是清洁后的命令。

## 3. 回归覆盖

新增 `tests/test_test_evidence.py`，使用临时目录和 fixture 卡，不触碰业务仓，覆盖：

1. 纯命令；
2. 一对 Markdown 反引号包裹的命令；
3. 闭合行内代码后带中文括号说明；
4. pytest `::` 节点 ID；
5. 未包裹命令内部 shell 反引号保持不变；
6. 无测试声明的既有放行语义。

## 4. 独立验证证据

- `bash -n scripts/test-evidence.sh`：通过。
- `python3 -m pytest tests/test_test_evidence.py -q`：`6 passed`。
- `python3 -m ruff check tests/test_test_evidence.py`：`All checks passed!`。
- 用 xy060 卡原文运行解析探针时，证据头已提取为：`uv run pytest tests/admin/test_library.py tests/admin/ -q`；说明文本未进入命令。该探针工作目录不是 xianyu 业务 worktree，随后因测试路径不存在退出 4，此结果不作为业务测试结果。

## 5. 后续

修复提交并推送后，让 Engine 按正常流程自然重审当前 xy060；若看板卡状态已为「打回」，只使用带 `CCC_BOARD_TOKEN` 的正规 redispatch，不改卡正文、不手工改状态。
