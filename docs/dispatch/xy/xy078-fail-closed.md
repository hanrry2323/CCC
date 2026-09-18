# 任务卡 xy078 · 产线失败 fail-closed（占位文件与 0 字节不再报成功）

> 关联：xy-plan-011（内容产线架构 阶段0 P0）· 执行体：DSH · 验收：DSH · 状态：打回（CC 审核不通过） · 派发：engine · 项目：xy · 日期：2026-09-18 · 版本：xy078 · 状态版本：5
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）
> 依赖：无（本卡是 xy-plan-011 全部后续卡的前置）

## 目标

把闲鱼视频产线的「失败」变成**真失败**。现在全管线失败时代码写一个 47-57 字节的文本占位文件冒充 mp4，并返回 `success=True`，导致 `data/videos/` 里 154 个 mp4 有 152 个是假文件、两个任务的 `final.mp4` 是 0 字节——而每一次都被记为成功。

改完后：**产线任何环节失败，必须返回失败态，绝不返回成功。** 这是 xy-plan-011 §五之二 防乐观评分第 8 条（「无产物不给分」）的前提——占位文件若仍报成功，后续任何质量分数都会被假成功污染。

## 实现要求

1. **`src/xianyu/content/video.py` 三处改动**：
   - `_mock_result()`（约 :1100）：`WorkerResult(success=True, ...)` → `success=False`，失败原因写入 `error` 字段（该字段已存在于 `src/xianyu/core/base_adapter.py:17` 的 `WorkerResult`，勿新增字段）。`data` 里保留 `video_path` 指向占位文件，但**必须**带 `mock: True` 与 `fallback_reason`（现成字段），让消费方仍能定位占位文件排查问题。
   - `run()` 的管线异常分支（约 :194 `fallback = self._write_mock(...)`）：同样改为 `success=False` + `error=str(exc)`。
   - `_write_mock()`（约 :1086）**继续保留占位文件写入**，不改删除——占位文件是有价值的诊断物证（152 个历史假视频就是靠它定位的），删了就没了。
2. **失败原因必须可区分三类**（写进 `fallback_reason`，机器可判）：`input_invalid`（输入校验不通过，:152 调用点）/ `pipeline_error`（管线抛异常，:194 调用点）/ `artifact_invalid`（产物为 0 字节或文本占位）。
3. **产物有效性判定新增一个明确函数**（建议 `_is_valid_artifact(path)`）：0 字节、无扩展名 mp4 的纯文本内容、`[MOCK VIDEO]` 前缀均判无效。**无效产物一律不得返回 `success=True`**——这是本卡的守门函数，后续卡都依赖它。
4. **下游消费者必须逐个核对**（禁止只改这一个文件就收工）：全文 grep `WorkerResult` 的所有调用方，确认每一处都能正确处理 `success=False`。重点核对：`openclaw/` 的 worker 调用链、`admin/` 前端取视频接口的错误分支、`workspace/outputs/` 的产物归档逻辑。**任一消费方在 `success=False` 时崩溃、或把失败产物当成功继续传播，即判本卡未完成。**
5. **新增测试** `tests/content/test_video_fail_closed.py`（目录 `tests/content/` 已存在，同族已有 8 个测试文件），至少覆盖：
   - 输入校验失败 → `success is False` 且 `fallback_reason == "input_invalid"`
   - 管线抛异常 → `success is False` 且 `error` 非空
   - 0 字节 mp4 → `_is_valid_artifact` 返回 False
   - 文本占位 mp4（`[MOCK VIDEO] ...`）→ `_is_valid_artifact` 返回 False
   - 正常产物 → `success is True` 且 `mock is False`（**正向用例必须有，防改坏正常路径**）
6. **方案关联卡登记（Q1 前置，模板纪律第 5 条）**：同 commit 把 xy078 追加进 `docs/projects/xy/plans/011-content-pipeline-quality-architecture.md` 的 §十二「阶段 0」小节（先 grep 实际文本再 replace，勿盲替换）。

## 红线

1. **禁止删除任何历史占位文件**（`data/videos/` 152 个）。它们是本卡的证据，删了就无法验证改动生效。
2. 只动 `src/xianyu/content/video.py` + 新增测试文件 + `docs/projects/xy/plans/011-*.md` 的关联卡行；**不动** `src/xianyu/content/writer.py` / `rewriter.py` / `router.py`（那是 xy081 的范围）、**不动** `video-pipeline/`（那是 xy079/xy080 的范围）、**不动** `scripts/daily/` 与任何 launchd 项（xy083）、**不动** M7 / Cookie / 发布相关任何文件。
3. **禁止为了让测试变绿而跳过用例、放宽断言或 mock 掉 `_is_valid_artifact`。** 本卡的测试就是要能杀死假成功，测不出来=没修。
4. **禁止改动 `config.env` 任何值**，密钥只允许占位引用。
5. 禁止 force push。commit 用显式路径，禁 `git add -A`。

## 范围

- /Users/fan/program/apps/xianyu/src/xianyu/content/video.py
- /Users/fan/program/apps/xianyu/tests/content
- /Users/fan/program/apps/xianyu/src/xianyu/core/base_adapter.py

## 步骤

1. 读 `src/xianyu/content/video.py` 全文，确认 `_write_mock` / `_mock_result` 定义位置与 `:152`、`:194` 两个调用点的实际上下文（本卡行号是外脑读取时的实测值，可能漂移，以你实测为准）。
2. 实现 `_is_valid_artifact(path)`：0 字节、无 mp4 魔数（真 mp4 首 4 字节为 `ftyp`）、`[MOCK VIDEO]` 文本前缀均判无效。
3. 改 `_mock_result()` 与管线异常分支为 `success=False`，填 `error` 与 `fallback_reason` 三类之一。
4. **下游核对（不可跳过）**：grep 全仓 `WorkerResult` 调用方，逐个确认能处理 `success=False`；发现崩溃点就一并修（改动范围若超出本卡「范围」段，须在回写信封里列明并请机审裁决）。
5. 新增 `tests/content/test_video_fail_closed.py`，5 个用例按实现要求第 5 条写，含正向用例。
6. 跑 `pytest tests/content/ -q` 全绿；再跑一次全量 `pytest -q` 确认无回归（若全量耗时过长，至少跑 `pytest tests/content/ tests/video/ tests/core/ -q`）。
7. **历史假视频显形验证**：跑 `ls -la data/videos/ | head` 与占位文件计数命令，在信封里记录改动后它们被识别为无效的计数（预期 152 个）。**这个数字变大/被报为失败是正确结果，不是回归**——xy-plan-011 阶段 0 的设计目的就是让真值显形。
8. 登记 011 关联卡（实现要求第 6 条）。
9. commit（显式路径）+ push 到当前 worktree 分支，然后写信封。

## 验收标准

1. `pytest tests/content/test_video_fail_closed.py -q` 全绿，且 5 个用例齐全（含正向用例）。
2. 输入校验失败路径返回 `success is False` 且 `fallback_reason == "input_invalid"`（测试断言可核）。
3. 管线异常路径返回 `success is False` 且 `error` 字段非空（测试断言可核）。
4. 0 字节 mp4 与 `[MOCK VIDEO]` 文本占位 mp4 均被 `_is_valid_artifact` 判无效（测试断言可核）。
5. **正向用例通过**：正常产物仍返回 `success is True` 且 `mock is False`——改坏正常路径即打回。
6. `git diff --stat` 改动范围 ⊆ 本卡「范围」段 + 新增测试文件；`config.env` 零改动。
7. `data/videos/` 历史占位文件**未被删除**（改动前后文件计数一致）。
8. 信封里含下游消费方核对清单（逐个列调用方 + 处理 `success=False` 的方式）。

## 回写要求（信封命令级 · 必须照做）

执行完成后，先 `cd /Users/fan/program/apps/.ccc-wt/xy/xy078`（workdir 根），再写信封文件：

信封文件：文件名逐字 `.ccc-result.md`，位置=当前目录（workdir 根）。
用你习惯的方式写入以下内容骨架（节名不带井号前缀，避免干扰卡解析）：

执行结果信封
  0 卡标题复述：复述任务卡标题
  1 探针输出：贴关键命令与输出（改动的文件、_is_valid_artifact 的实测判定、占位文件计数命令与结果、git diff --stat）
  2 自测输出：贴 pytest 命令与退出码（tests/content/ 定向 + 全量或 tests/content+video+core）
  3 维护区四问：方案同步（011 关联卡是否已登记）/ 教训沉淀 / 档案README / 线路图，各带 是否/有无 与说明

写完必须 `ls -la .ccc-result.md` 确认落盘；不落信封 = 判空转失败 rc=64。信封不进业务仓 git。

卡文件本身不要改状态、不要填回写区——卡状态与回写区由引擎收单时代写（A2 契约）。写完信封即停手；业务代码改动 commit+push 到当前 worktree 分支即可。

## 维护区

1. **方案同步**：xy-plan-011 状态/关联卡是否已同步？[是]
   - 说明：xy-plan-011 阶段 0 首卡，方案状态已推进「部分执行」（commit 82d7599f9），关联卡已登记。
2. **教训沉淀**：本卡是否产出可复用教训？[有]
   - 说明：A1 传输闸门硬编码白名单与引擎权威分类器不一致，导致 48 轮死复跑（rc=64 假拦截）。根修 commit aabc2aba9（两处执行器统一调 classify_annotation）。教训已入本卡 commit message，属底座级教训，建议同步 ccc-plan-055 缺口清单。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：只改 src/xianyu/content/video.py + 新增 tests/content/test_video_fail_closed.py + 对齐 tests/test_cinematic_video.py 旧断言。未改项目结构/技术栈/路径。
4. **线路图**：项目近况/下一步是否变化？[是]
   - 说明：阶段 0 收口（fail-closed 生效，假成功不再污染质量分）。下一批为阶段 1：xy079（CLIP 实跑 + pass_full/pass_partial 双口径）、xy080（内容维打分器 + 8 条防乐观测试全绿）。

## 人工批注


（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：Q1 方案同步校验失败。方案关联卡「无（拍板前不动手；实施按「功能卡」拆解，见 §七）」中不包含本卡 ID「xy078」；Q2 声明了有教训沉淀[有]，但说明中未引用任何 docs/notes/*.md 或 lessons.md 文件；Q4 声明更新了线路图[是]，但指定的文件 docs/roadmap.md, docs/projects/xy/README.md 在当前分支上没有检测到相对 origin/main 的修改
