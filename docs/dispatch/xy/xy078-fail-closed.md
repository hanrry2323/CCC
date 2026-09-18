# 任务卡 xy078 · 产线失败 fail-closed（占位文件与 0 字节不再报成功）

> 关联：xy-plan-011（内容产线架构 阶段0 P0）· 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-18 · 版本：xy078 · 状态版本：9
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

1. **方案同步**：[是] xy078 已登记于 `xy-plan-011`：头行「关联卡」列 `xy078（阶段0 首卡，人审重派中，代码已交付待合入）`，且 §十二「阶段 0」小节含 `**xy078 · 产线失败 fail-closed（P0，首卡）**`（实测 `:295`，由方案 v2 落库 commit `331b37beb` 写入）——Q1 前置成立；本轮**未改写 CCC 方案文件**（该仓不在本 run 授权、亦不在卡「范围」白名单），仅申报 §1.7-D/E 两项口径漂移待引擎代写。
2. **教训沉淀**：[无] 已有 `docs/notes/2026-09-18-xy078-lessons.md`（2468 B，2 条底座级教训：shell 白名单与引擎权威分类器不一致致 48 轮死复跑、A2 契约与 `consume_once` 互斥致收单死锁）；本信封追加**代码级教训一条**：失败态与产物态必须同源校验——占位文件与 `success` 解耦即产生 152 例假成功，且旧测试把 bug 固化为断言（`assert result.success is True`）会让回归隐形，故守门函数与其测试必须同卡落地。
3. **档案/README**：[否] 未改变项目结构/技术栈/路径：无新增模块或目录、`WorkerResult` 契约字段未增未减（复用既有 `error`），README 无口径需改；模块级文档已随 `9cb0043` 把 fail-closed 契约（三类 `fallback_reason` + `_is_valid_artifact` 守门口径 + 占位文件保留为物证）写入 `video.py` docstring，避免后续读者据旧注释把失败路径改回 `success=True`。
4. **线路图**：[是] 阶段 0 代码面收口：守门函数 `_is_valid_artifact`（`video.py:1108`）就位，可作 xy-plan-011 阶段 1+（xy079 CLIP 实跑、xy080「无产物不给分」打分器）的判产前置；下一步与 §1.7 登记项同步：先合入本卡（代码待合业务仓 main），再开 xy079/xy080，并把 tts 同型 fail-open（B）、admin/sau 有效性口径（C）三条补成后续卡。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：REJECT 预算耗尽，待人工
- 轨迹恢复注记（2026-09-18 外脑）：本节曾被 commit cb42e4128 以手工回写整节删除，
  原文按 git 历史逐字恢复（该提交信息称「关闭卡」但卡头状态未改，且删审计轨迹
  违反机审区不可改写原则）。机审历史结论保留不改写，处置走人审重派正规通道。

## 回写区

## 0. 卡标题复述

**xy078 · 产线失败 fail-closed（占位文件与 0 字节不再报成功）**

## 1. 探针输出

### 1.1 批注要求的前置动作（先确认既有 commit，动手前跑）

```
$ git log --oneline origin/main..HEAD
9cb0043 docs(xy078): video.py 模块 docstring 同步 fail-closed 契约   ← 本轮追加（纯注释）
0825288 style(xy078): ruff 修复——OSError 别名合并（UP024）与测试文件导入块格式（I001）
86882a5 test(xy078): 旧测试对齐 fail-closed 契约——mock 路径断言成功态为 False
aee2d24 feat(xy078): 产线失败 fail-closed——占位文件与 0 字节不再报成功
```

批注所称「3 commit：aee2d24 feat + 86882a5 test + 0825288 style」**逐字命中**，三者均在位且历史未被改写；本轮 push 为 fast-forward（`0825288..9cb0043`），无 `--force`（见 §4）。

### 1.2 改动的文件（`git diff bc75287..HEAD`；bc75287 = 卡取证基线 = 业务仓取证 HEAD）

```
 src/xianyu/content/video.py             |  67 +++++++++-
 tests/content/test_video_fail_closed.py | 219 ++++++++++++++++++++++++++++++++
 tests/test_cinematic_video.py           |  28 ++--
 3 files changed, 298 insertions(+), 16 deletions(-)
```

`config.env` 零改动：`git diff bc75287..HEAD --name-only | grep -i config.env` → **空输出**（实测）。白名单文件 `src/xianyu/core/base_adapter.py` **零改动**——`WorkerResult.error` 既已存在（`openclaw/worker_base.py:20`、`core/base_adapter.py:22`），按卡「勿新增字段」要求不动。

### 1.3 `_is_valid_artifact` 实测判定（守门函数，现行位点 `src/xianyu/content/video.py:1108`）

对权威仓历史产物**只读**跑本卡守门函数：

```
$ .venv/bin/python - <<'PY'   # 遍历 /Users/fan/program/apps/xianyu/data/videos/*.mp4
total mp4 in data/videos      : 154
_is_valid_artifact -> INVALID  : 152      ← 卡预期「152 个假文件」精确命中
  of which [MOCK VIDEO] text   : 152
  of which 0-byte              : 0
_is_valid_artifact -> VALID    : 2
sizes of INVALID (sample 5)    : [('00c5096b.mp4',57),('0289d33a.mp4',57),('02b280fc.mp4',47),
                                  ('05c10994.mp4',57),('072c10a6.mp4',57)]
VALID files                    : [('a78e25be.mp4',237146),('cb6fb11c.mp4',1333612)]
```

0 字节 `final.mp4` 同口径（卡「两个任务的 final.mp4 是 0 字节」精确复现）：

```
size=       0 valid=False 6ca86475/final.mp4
size=       0 valid=False a7c83511/final.mp4
size= 1333612 valid=True   cb6fb11c/final.mp4
```

判定三类无效（`:1108` 起）：文件不存在/非文件 → False；`st_size == 0` → False；头 12 字节以 `b"[MOCK VIDEO]"` 起 → False；`b"ftyp" not in head[:8]` → False。

### 1.4 端到端失败路径实跑（直接调 `execute()`，非测试桩）

```
LIVE PROBE 输入校验失败路径:
  success        = False                   ← 改前为 True
  error          = 'No image paths provided'
  fallback_reason= input_invalid
  mock           = True
  video_path kept for diagnosis = True     ← 占位文件路径仍保留（实现要求 1 后半）
  ASSERT OK: 失败不再报成功
```

三类 `fallback_reason` 机器可判（**现行实测位点**，含 `9cb0043` 注释后漂移）：`input_invalid` → `video.py:1161`（`_mock_result` 定义 `:1151`；卡所指 `:152` 调用点现 `:158`）；`pipeline_error` → `video.py:222`（管线异常 `except` 分支；卡所指 `:194` 调用点现 `:214`）；`artifact_invalid` → `video.py:188`（守门 `if not self._is_valid_artifact(outcome.path)` 在 `:179`，位于 `process()` 成功之后、成片落盘之前）。漂移与卡步骤 1「本卡行号可能漂移，以你实测为准」一致，非逻辑偏移。

### 1.5 占位文件计数命令与结果（红线 1：未删任何历史占位文件）

```
$ ls /Users/fan/program/apps/xianyu/data/videos/*.mp4 | wc -l            → 154（改动前后一致）
$ find data/videos -maxdepth 1 -name "*.mp4" -size -100c | wc -l         → 152（占位数不变）
$ ls -la data/videos/ | head -4
drwxr-xr-x  156 fan  staff  4992 Sep 10 20:41 .
-rw-r--r--    1 fan  staff    57 Aug  8 13:01 00c5096b.mp4   ← mtime 远早于本 run，未被触碰
```

`_write_mock()`（现 `video.py:1139`）占位写入逻辑**保留未删**（实现要求 1 第 3 点：占位文件是诊断物证）。

### 1.6 下游消费方核对清单（实现要求 4 / 验收 8；逐位点，均可命令复现）

| # | 消费方位点 | 处理 `success=False` 的方式 | 判定 |
|---|---|---|---|
| 1 | `orchestrator/pipeline.py:609` `_run_stage` | `if not result.success: raise WorkerError(f"阶段 {stage.name} 失败: {result.error}")` | 收口为可重试错误，不崩 ✅ |
| 2 | `orchestrator/pipeline.py:284-294` + `:317` + `:449` | `WorkerError` 被捕获 → `PipelineResult(success=False, retryable=True)`；`stage_outputs[stage.name]=out` **仅成功路径执行** → 失败时无 `"video"` 键 → 发布闸门 `if pipeline=="video" and "video" in stage_outputs` 不可达 | 失败产物不向 publish 传播 ✅ |
| 3 | `core/base_adapter.py:81-86` `WorkerAdapterWrapper.run` | `WorkerResult(success=wr.success, data=wr.data, error=wr.error)` 原样透传 | ✅ |
| 4 | `core/base_adapter.py:52` `health_check` | `return r.success` | ✅ |
| 5 | `openclaw/worker_base.py:47-54` `BaseWorker.run` | 成功路径原样返回（`success=False` 保留，仅补 `duration`）；异常路径 `return WorkerResult(success=False, ...)` | ✅ |
| 6 | `health.py:43-47` | `if health_result.success: … else: issues.append(f"HealthWorker 失败：{health_result.error}")` | 有错误分支 ✅ |
| 7 | `cli.py:118-136` | 逐 stage `data.get("success")` → `OK/FAIL/SKIP` 三态；末段成功 `return 0`，否则打印 `result.error` 且 `return 1` | 双态齐 ✅ |
| 8 | `admin/api/server.py` | `grep -rn "WorkerResult\|worker.execute\|\.success" admin/api/*.py` → **空输出**（不消费本卡契约）；取视频走文件系统扫描且带 `except OSError: has_video=False` + symlink 越界守卫（`:1484-1491`） | 不受影响 ✅（残留口径见 §1.7-C） |
| 9 | `scripts/bench_video.py:180-282` | 仅直调内部方法（`_build_scenes`/`_generate_tts`/`_build_ffmpeg_command`/`_run_ffmpeg`）；`grep -n "execute(\|\.success"` → 空输出 | 不消费 `execute()` 返回 ✅ |
| 10 | `bridge/sau_bridge.py:228-229` `upload_video` | 自带 `Path(video_path).exists()` 校验并返回 `success=False`；且位点 2 已保证 mock 路径不流入发布链 | ✅（有效性口径残留见 §1.7-C） |

`workspace/outputs/` 产物归档侧：写盘只发生在成功路径（`_land_final_video` 于 `:194` 调用，位于 §1.4 守门之后），失败路径不产生 `final.mp4`；0 字节历史 `final.mp4` 由 §1.3 第二组探针证实已被判无效。

### 1.7 疑似问题登记（数值/口径异常先标注，不当结论；均未越白名单修改）

| 编号 | 观察 | 证据 | 本卡处置 |
|---|---|---|---|
| A | `tests/openclaw/test_plugin_integration.py` 2 例在本 worktree 失败 | `ERR_MODULE_NOT_FOUND: Cannot find package 'typebox'`；worktree 无 `openclaw-plugin/node_modules`；主仓有 `.../xianyu/openclaw-plugin/node_modules/typebox`；两树 `dist/index.js` **byte-identical**（`cmp` → IDENTICAL），主仓侧 `node -e require(...)` → `LOAD_OK` rc=0 | 判为环境缺 gitignored npm 依赖，**非 xy078 回归**（本卡未触 `openclaw-plugin/` 任何文件，见 §1.2 三文件清单）；未修 |
| B | `content/tts.py:41-47` 仍对 `[MOCK AUDIO]` 文本占位返回 `success=True` | 直读源码 | 与本卡同型 fail-open，但不在卡白名单（卡只点名 `video.py`，红线 2 明示不动其他产线文件）→ **未改**，建议出后续卡 |
| C | 有效性口径残留两处：`admin/api/server.py:1738` `_has_video()` 对 0 字节 `final.mp4` 仍判「有视频」；`sau_bridge:228` 只判 `exists()` 不判内容有效 | 直读源码；admin 扫描源为 `video-pipeline/output`（`:51`） | 前者属 xy079/xy080 范围（红线 2 不动 `video-pipeline/`），后者属发布侧（红线 2 不动发布相关）→ 未改，纳入 Q4 线路图建议 |
| D | 011 方案内部口径漂移：§十二 阶段0 行仍写「**xy078 …· ✅ 已关闭**」，而头行 v5 已更正为「待合入（v4「已关闭」不实）」 | `sed -n '293,296p'` vs `sed -n '4p'` 实测对照 | 该文件在 CCC 主仓，**超出本 run 授权（仅 biz_worktree）与卡「范围」白名单** → 未改，申报引擎代写 |
| E | CCC `docs/projects/xy/README.md:48` 近况写「代码：`0825288` 已推」，而分支现 HEAD=`9cb0043` | `grep -n 0825288` + `git rev-parse --short HEAD` | 同 D：CCC 仓不在授权内 → 未改，申报引擎代写（卡步骤「线路图 diff 对齐」需引擎落笔） |
| F | 仓级 ruff 4 处报错，无一在本卡文件 | 2×W292 `tests/admin/test_preview_refresh.py:46`、`tests/admin/test_workflow_nodes.py:80`（基线 `bc75287` 时末字节已是 `0x6c`＝非本卡引入）；N802 `tests/storage/test_local_writer.py:134`；F841 `tests/test_orchestrator.py:175` | 全在卡白名单外 → 未改；本卡三文件 `ruff check` → `All checks passed!` rc=0 |

## 2. 自测输出

解释器：worktree 自带 `.venv/bin/python`（3.12.0 / pytest 9.0.3）。未安装任何新依赖、未用 `uvx`/临时环境（遵测试约束）。所有退出码为命令级实测。

| 命令 | 结果 | 退出码 |
|---|---|---|
| `pytest tests/content/test_video_fail_closed.py -q` | **6 passed** in 0.22s | **0** |
| `pytest tests/content/ -q` | **100 passed** in 4.62s | **0** |
| `pytest tests/content/ tests/video/ tests/core/ -q`（卡步骤 6 定向组合） | **394 passed, 3 skipped** in 17.71s | **0** |
| `pytest tests/test_cinematic_video.py -q`（旧断言对齐面复验） | **45 passed** in 2.27s | **0** |
| `pytest -q`（全量） | 2 failed, **834 passed**, 8 skipped in 85.05s | 1 |
| `ruff check src/xianyu/content/video.py tests/content/test_video_fail_closed.py tests/test_cinematic_video.py` | All checks passed! | 0 |

全量那 2 例失败**逐例归因已复现**（§1.7-A）：均在 `tests/openclaw/test_plugin_integration.py`，根因是 worktree 缺 gitignored `openclaw-plugin/node_modules`（`typebox` 不可解析）；同一 `dist/index.js`（`cmp` 判 IDENTICAL）在主仓侧 `LOAD_OK` rc=0。本卡 3 个改动文件全在 Python 侧，与该 node 用例无交集（`git diff bc75287..HEAD --name-only` → 3 文件，无 `openclaw-plugin/`）。

新增测试 `tests/content/test_video_fail_closed.py` 用例清单（卡实现要求 5 的 5 条 + 1 条守门补强，共 6 例，验收 1 要求「5 个用例齐全」已满足）：

| 用例 | 断言要点 |
|---|---|
| `test_input_validation_failure_returns_fail` | `success is False` + `fallback_reason == "input_invalid"` + `error` 非空 |
| `test_pipeline_exception_returns_fail` | `success is False` + `error == "simulated pipeline failure"` + `fallback_reason == "pipeline_error"` |
| `test_zero_byte_mp4_is_invalid` | `_is_valid_artifact` → `False` |
| `test_mock_placeholder_mp4_is_invalid` | `[MOCK VIDEO]` 文本占位 → `False` |
| `test_valid_artifact_returns_success` | **正向用例**：`success is True` + `mock is False` + `error == ""` |
| `test_invalid_artifact_returns_fail` | 管线未抛异常但产物 0 字节 → `artifact_invalid` + `success is False` |

红线 3 自查：无 skip、无放宽断言、未 mock 掉 `_is_valid_artifact`（正向用例喂**真 ftyp 字节**而非打桩绕过）。`9cb0043` 为纯注释 commit（其全部 `+/-` 行均落在模块 docstring 内，无一条可执行语句变更；改后 `tests/content/ + tests/test_cinematic_video.py` **145 passed**）。

## 批注落实

」段。
- 依批注「不重做已交付代码」：既有 3 个交付 commit 未重做、未回滚、未覆盖（复现见 §1.1）。
- 本轮唯一新增业务仓改动 = 1 个纯注释 commit `9cb0043`（性质与超范围申报见 §4 与「批注落实」第 3 条，请机审裁决）。
