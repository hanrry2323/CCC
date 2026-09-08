# xy060 Q2 教训引用契约修复与重派报告

日期：2026-09-05
状态：**部分完成（重派 → 机审因卡声明测试命令解析异常被截获打回，未假造结果）**

## 0. 指令与目标

按 `~/.ccc/instructions/2026-09-05-xy060-q2-contract-fix.md` 执行：修复 xy060 卡「前置机审与维护区契约」中 Q2 的教训引用规则（选 `[有]` 必须引用 CCC 主仓真实存在的 `docs/notes/YYYY-MM-DD-*.md` 或 `lessons.md` 路径），再用正规重派恢复流程。未改 xianyu 业务代码、未删除 worktree 提交、未手工写卡回写区、未手工写机审区。

## 1. 契约规则修改

- 文件：`docs/dispatch/xy/xy060-content-library-api.md` §「前置机审与维护区契约」第 2 问。
- 旧：说明是否产生可复用的目录扫描/坏文件容错教训；无则写 `[无]` 及理由。
- 新：Q2 选择 `[有]` 时，说明必须引用 CCC 主仓中真实存在的 `docs/notes/YYYY-MM-DD-*.md` 或 `lessons.md` 路径，并说明该文档与本卡的复用教训；若没有真实文档，必须选择 `[无]` 并说明理由，不得以未落盘的口头教训或其他过程记录代替。
- 校验：`python -m server.board.validate docs/dispatch` 通过；`validate task cards (docs/dispatch)` Passed。
- 提交：`78c28f4ff`（`docs(xianyu): specify xy060 lesson citation contract`，push origin/main）。

## 2. 正规重派

- 方式：`bash scripts/redispatch-card.sh xy060`，token 经 `CCC_BOARD_TOKEN` 环境变量注入，token 仅存调用进程环境与请求头，未写入文件/脚本/日志。
- 返回：`{"ok": true, "id": "xy060", "from": "打回", "to": "待分派", ...}`。
- Engine 自动认领：看板显示 `xy060` → `执行中`、`board_column=执行中`、`executor=DSH`，`started_at` 更新；未手工启动 DSH。

## 3. 重派后流程与机审结果

Engine 重派后 DSH 复用既有业务提交，重跑测试并重新生成 `.ccc-result.md`（Q2 按新契约选择 `[无]`，因 CCC 主仓已有真实教训文档 `docs/notes/2026-09-05-xy060-content-library-lesson.md` 但不适用本卡新增沉淀，具体理由见卡回写区「维护区」第 2 问）。回写后后段 cc-auditor 拦截：

- 拦截点：cc-auditor 机械门禁二（test-evidence）——卡声明测试命令解析异常。
- 证据：`~/.ccc/logs/exec/xy060.test-evidence.log`：
  - `test-evidence.sh: eval: line 66: unexpected EOF while looking for matching '`
  - `test-evidence.sh: eval: line 67: syntax error: unexpected end of file`
  - `=== exit_code=1 ===`
- 根因：卡「门禁」节测试命令 `uv run pytest tests/admin/test_library.py tests/admin/ -q`（若仓库现行入口不同，先核实后使用等价命令）行尾挂着一个未配对的后引号（模板尾部遗留），被 `test-evidence.sh` 的第 49 行 `strip(chr(96))`（`strip` 只剥字符串两端、剥不掉命令串内部的后引号）截获为未闭合反引号，导致 `eval` 语法错误、测试证据失败。DSH 业务 worktree 内 `98 passed`（run15 日志）不受影响；失败发生在主仓卡门禁命令解析，与业务实现无关。

## 4. 结果与后续

- 新契约规则已生效并持久（Engine 回写未覆盖该契约段）。
- 重派流程走通，Engine 自动认领、DSH 复用既有提交、Q2 按契约给出真实 `[无]`。
- 本次打回是「门禁测试命令解析异常」这一真实机械门禁失败，已保留原始证据，**未**修改卡绕过、未假造机审通过。修复方式属于卡正文「门禁」节格式（去掉行尾多余反引号）而非本指令红线范围，留待后续按流程处理。

## 5. 证据索引

- 契约提交：`git show 78c28f4ff`。
- 重派返回：`{"ok": true, "from": "打回", "to": "待分派"}`。
- Engine 认领：看板 `xy060` 状态 `执行中`（`curl http://192.168.3.116:7788/cards`）。
- 机审打回证据：`/Users/fan/.ccc/logs/exec/xy060.test-evidence.log`、`/Users/fan/.ccc/logs/exec/xy060-audit-verdict.md`。
- 维护区四问（重派后回写）：`docs/dispatch/xy/xy060-content-library-api.md`「维护区」第 2 问 = `[无]` 并说明理由。

未记录任何 token/key。
