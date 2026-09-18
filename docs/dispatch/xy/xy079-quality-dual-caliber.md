# 任务卡 xy079 · 视频质量双口径 + CLIP 实跑（skip 不再静默通过）

> 关联：xy-plan-011（内容产线架构 阶段1 P1）· 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-18 · 版本：xy079 · 状态版本：2
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）
> 依赖：xy078（阶段 0 fail-closed 前置；xy078 未关闭前本卡不被派发属预期，011 明令不得跳序）

## 目标

让质量检查的「跳过」显形、让画面-话题相关度（CLIP）真实可跑。现在 `scripts/check_video_quality.py` 的 ML 两项（视听一致 CLIP 相关度、差异化）在模型缓存缺失时静默 `ok=None`，汇总时不扣分，读者把「9 项技术参数达标」误读成「全部通过」——这是 xy-plan-011 §一 断链 2 的病灶，也是 §五之二 防乐观第 1 条（skip 永不静默通过）的直接对象。

改完后：**任何 skip 都在汇总里显式可见，有 skip 时 `pass_full` 恒 False；CLIP 用真实模型跑出数字。**

## 实现要求

1. **CLIP 模型缓存补齐（一次性）**：sentence-transformers 已装 2.7.0，但 `~/.cache/huggingface/hub/` 只有 bge-m3、无 clip-ViT-B-32。2017 实测 huggingface.co 直连不可达（curl 000）、hf-mirror.com 可达（200）——用 `HF_ENDPOINT=https://hf-mirror.com` 走镜像完成下载，并 `ls ~/.cache/huggingface/hub/` 自证落盘。若镜像也失败：停止并在信封如实记录，**禁止把「下载失败」处理成「继续静默 skip」**。
2. **`_load_sentence_transformers()`（约 :362）去静默**：库已装而模型缓存缺失时，不得返回 None 让调用方记「not installed」了事——结果 `detail` 必须写明真实原因（含 `model_cache_missing` 字样）并附可操作下载命令，与「库未安装」可区分。
3. **双口径汇总函数（核心交付）**：新增 `summarize_quality(results) -> dict`，输出六字段 `total/fail_count/skip_count/skip_names/pass_full/pass_partial`。口径逐字执行（§五 铁律 1）：`pass_full = (fail_count == 0 AND skip_count == 0)`；`pass_partial = (fail_count == 0)`；有 skip 时 `skip_names` 非空。接入 `--json` 输出（顶层加 `summary` 键）与 `--report-md` 报告（报告标题行必须显示用的是哪个口径；`pass_full=False` 时禁止出现「全部通过」字样）。
4. **下游消费核对（禁止只改这一个文件就收工）**：grep 全仓谁在消费 check_video_quality 的输出（subprocess 调用 / `--json` 解析 / 报告读取，含 video-pipeline 侧）。有消费方按旧单口径解读的，列清单并最小对齐到 `pass_full`；超出本卡范围时在信封写明请机审裁决。
5. **新增测试** `tests/video/test_quality_dual_caliber.py`（目录已存在），至少 6 用例：
   - 全 pass 输入 → `pass_full` True 且 `pass_partial` True 且 `skip_names` 空
   - 1 项 `ok=None`（skip）→ **`pass_full is False`** 且 `skip_names` 含该项名（§五之二 条款 1 的失败测试，必须有）
   - 1 项 `ok=False` → `pass_partial` False 且 `pass_full` False
   - 模型缺失路径：`detail` 含 `model_cache_missing` 且不含 `not installed`
   - `summarize_quality` 六字段完整性断言（缺一即测试红）
   - 正向回归：既有 9 项技术参数判定不因本次改动改变
6. **真实样本实跑**：`data/videos/` 有 2 个真实 mp4（>1000 字节，其余 152 个是占位文本属 xy078 已显形的历史真值，不许动）。取一个真实 mp4 配主题跑 `python3 scripts/check_video_quality.py <真实mp4> --json`，把视听一致项的 `value` 数字与 `detail` 原样进信封。预期 value 为 0-1 区间数字。**跑不出数字就在信封写失败，禁止拼接/伪造 JSON 凑验收。**

## 红线

1. 禁止改 `src/xianyu/content/video.py`（xy078 范围）与 `src/xianyu/content/writer.py`/`rewriter.py`/`router.py`（xy081 范围）。
2. 禁止删除或改写 `data/videos/` 任何文件（计数改动前后一致）。
3. 禁止为让 `pass_full` 变绿而放宽 skip 判定、mock 掉 CLIP、或把 skip 改记为 pass。测试要能杀死「静默通过」，测不出来=没修。
4. 禁止改动 `config.env` 任何值。禁止 force push；commit 显式路径，禁 `git add -A`。
5. 模型权重只落 `~/.cache/huggingface/hub/`，禁止拷进业务仓。

## 范围

- /Users/fan/program/apps/xianyu/scripts/check_video_quality.py
- /Users/fan/program/apps/xianyu/tests/video

## 步骤

1. 读 `scripts/check_video_quality.py` 全文，确认 `_load_sentence_transformers` / `check_clip_alignment` / `check_uniqueness` / `main` 实际结构（卡内行号是外脑 09-18 实测值，可能漂移，以实测为准）。
2. 镜像下载 clip-ViT-B-32 并自证缓存（实现要求 1）。
3. 实现要求 2（去静默）。
4. 实现要求 3（summarize_quality + 接入两种输出）。
5. 实现要求 4（下游 grep 核对，清单进信封）。
6. 写 `tests/video/test_quality_dual_caliber.py` 6 用例。
7. `pytest tests/video/ -q` 全绿；再跑回归（全量或至少 tests/video + tests/content + tests/core）。
8. 真实样本实跑（实现要求 6），数字原样进信封。
9. commit（显式路径）+ push 到当前 worktree 分支，然后写信封。

## 验收标准

1. `pytest tests/video/test_quality_dual_caliber.py -q` 全绿且 6 用例齐全（含条款 1 失败测试）。
2. `--json` 输出含 `summary` 六字段；机审可复跑：构造含 skip 输入 → `pass_full is False`。
3. `ls ~/.cache/huggingface/hub/` 可见 clip-ViT-B-32；真实样本视听一致项 `value` 为数字、`detail` 不含 "not installed"。
4. `git diff --stat` 改动 ⊆ 范围段 + 新增测试文件；`video.py`、`config.env` 零改动。
5. `data/videos/` 文件计数改动前后一致。
6. 信封含下游消费方核对清单与真实样本实测数字原样粘贴。

## 回写要求（信封命令级 · 必须照做）

执行完成后，先 `cd /Users/fan/program/apps/.ccc-wt/xy/xy079`（workdir 根），再写信封文件：

信封文件：文件名逐字 `.ccc-result.md`，位置=当前目录（workdir 根）。
用你习惯的方式写入以下内容骨架（节名不带井号前缀，避免干扰卡解析）：

执行结果信封
  0 卡标题复述：复述任务卡标题
  1 探针输出：贴关键命令与输出（缓存 ls、--json 的 summary 片段、真实样本视听一致项、git diff --stat、data/videos 计数）
  2 自测输出：贴 pytest 命令与退出码（tests/video/ 定向 + 回归套件）
  3 维护区四问：方案同步（011 卡头关联已含 xy079，是否无需新增）/ 教训沉淀 / 档案README / 线路图，各带 是否/有无 与说明

写完必须 `ls -la .ccc-result.md` 确认落盘；不落信封 = 判空转失败 rc=64。信封不进业务仓 git。

## 维护区

1. **方案同步**：[是] 无需新增。xy-plan-011 卡头关联已含 xy079（依赖关系「xy078 阶段 0 前置」也已在 011 内维护）；本卡交付（双口径汇总 + CLIP 实跑）即 011 §一 断链 2 与 §五之二 防乐观第 1 条的落地，未新增/变更方案文档，无平行方案需同步。
2. **教训沉淀**：[有] 两条，均已写入 `scripts/check_video_quality.py` 函数 docstring 作为常驻注释：(a) **旧代码 `SentenceTransformer(..., local_files_only=True)` 在 ST 2.7.0 下必抛 TypeError**（该版本 `__init__` 无此形参），异常被外层吞掉后落入联网分支，而 2017 实测 huggingface.co 不可达，整条 CLI 可挂 600s+——正确做法是把 HF 缓存快照目录直接当 `model_name_or_path` 传入（零网络，实测 2.2s 加载）。(b) **运行期设 `os.environ["HF_HUB_OFFLINE"]` 是空转**：`huggingface_hub.constants` 在 import 期已固化该值。教训泛化：lazy-import + 宽 except 会把「配置/版本不匹配」伪装成「功能不可用 skip」，去静默必须连加载路径一起查。
3. **档案/README**：[否] 本卡未新增模块、未改公共接口签名（`summarize_quality` 为脚本内新函数），未改 `--json` 既有键结构（仅顶层加 `summary`），README/ARCHITECT 现有描述不构成失真；`docs/projects/README.md` 属 CCC 仓、越卡范围未动。
4. **线路图**：[否] 本卡关闭后，011 阶段 1 的「质量检查显形」断链闭合；下一环暴露出的待裁决项 = `video-pipeline/render_all_templates.py` 仍按退出码单口径判 `verified`（把 exit 2 全跳过当通过），建议另卡处理（改其消费 `--json summary.pass_full`，需动 video-pipeline 侧，越本卡白名单，已在 1.7 清单写明请机审裁决）。GOAL.md 未改动，线路图增量由 Engine 回写卡时体现。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

## 0. 卡标题复述

任务卡 xy079 · 视频质量双口径 + CLIP 实跑（skip 不再静默通过）

## 1. 探针输出

### 1.1 CLIP 模型缓存自证（实现要求 1）

```
$ ls -la ~/.cache/huggingface/hub/
drwxr-xr-x  4 fan  staff  128 Jul 15 21:54 models--BAAI--bge-m3
drwxr-xr-x  5 fan  staff  160 Sep 18 20:44 models--sentence-transformers--clip-ViT-B-32

$ ls ~/.cache/huggingface/hub/models--sentence-transformers--clip-ViT-B-32/snapshots/
327ab6726d33c0e22f920c83f2ff9e4bd38ca37f

$ du -sh ~/.cache/huggingface/hub/models--sentence-transformers--clip-ViT-B-32/
579M	/Users/fan/.cache/huggingface/hub/models--sentence-transformers--clip-ViT-B-32/
```

快照内 `modules.json` 与 `0_CLIPModel/` 齐在（脚本判缓存完整性的两个判据），权重只落 HF 缓存、未拷进业务仓。落盘时间戳 Sep 18 20:43–20:44 = 前次执行经 hf-mirror 下载，本次复核结构完整可加载（见 1.4 实跑）。

### 1.2 真实样本实跑（实现要求 6）— 数字原样粘贴

样本：`/Users/fan/program/apps/xianyu/data/videos/cb6fb11c.mp4`（1333612 字节，1080×1920 h264，23.5s）。主题取自该成片生成时的真实 trace（`logs/app.log:3447` trace_id=3a55b153dd8b → 标题「旧镜头捡漏翻新：一颗85mm人像头，转手赚800」），非人为拼接。

```
$ python3 scripts/check_video_quality.py .../cb6fb11c.mp4 --json --topic "旧镜头捡漏翻新：一颗85mm人像头，转手赚800"
EXIT=1   （耗时 1m26s；CLIP 走本地快照，加载成功）
```

视听一致项（原样）：

```json
{
  "name": "画面-话题相关度",
  "ok": true,
  "value": 0.2808,
  "threshold": "CLIP score ≥ 0.25",
  "detail": "model=sentence-transformers/clip-ViT-B-32 frames=3 avg=0.2808 topic='旧镜头捡漏翻新：一颗85mm人像头，转手赚800' scores=['0.301', '0.272', '0.269']"
}
```

`value` 为 0–1 区间裸数字 ✅；`detail` 含真实模型名与逐帧分数，不含 "not installed" ✅。同一次输出中「视频差异化」因单视频仍为 `ok=null` 的显式 skip，汇总如实反映：

```json
"summary": {
  "total": 11,
  "fail_count": 5,
  "skip_count": 1,
  "skip_names": ["视频差异化"],
  "pass_full": false,
  "pass_partial": false
}
```

（5 个 fail 是该历史样片本身技术参数不达标——码率 0.45Mbps、时长 23.5s、无伴生字幕/BGM——属既有真值，非本次改动引入，也不动。）

### 1.3 `--report-md` 标题行口径标注（实现要求 3）

同一样本报告真实输出标题行 + skip 显形：

```
# 视频质量量化检测报告 · 判定口径: pass_full=False（fail=5 skip=1） · 对照口径 pass_partial=False
- **pass_full（零 fail 且零 skip）**: False
- **pass_partial（零 fail）**: False
- **被跳过项（未判定，不等于通过）**: 视频差异化
- **结论**: 不达标 —— 5 项失败，两口径均不通过
```

全文无「全部通过」字样 ✅（该字样仅在 `pass_full=True` 分支出现，测试双向锁死）。

### 1.4 skip 必杀 pass_full（验收标准 2 · 机审可复跑）

```
$ python3 -c "... summarize_quality(9 项 ok=True + 1 项 ok=None)"
{'total': 10, 'fail_count': 0, 'skip_count': 1, 'skip_names': ['画面-话题相关度'], 'pass_full': False, 'pass_partial': True}
```

即卡要杀的病灶场景：9 项技术参数全达标 + 1 项 skip → 旧读法「全过」，现 `pass_full is False`。

### 1.5 `git diff --stat`（origin/main..HEAD）

```
 scripts/check_video_quality.py           | 308 +++++++++++++++++++++---
 tests/video/test_quality_dual_caliber.py | 400 +++++++++++++++++++++++++++++++
 2 files changed, 671 insertions(+), 37 deletions(-)
```

改动 ⊆ 卡范围白名单（`scripts/check_video_quality.py` + `tests/video`）。红线核对：`video.py` / `writer.py` / `rewriter.py` / `router.py` / `config.env` 零改动（`git diff --name-only origin/main..HEAD | grep -E "video\.py|config\.env"` 输出为空）。

### 1.6 `data/videos/` 计数（红线 2）

- 主仓（真实样本所在）：改前改后均 **154** 个（2 个真实 mp4 + 152 个历史占位），时间戳仍为 Sep 10，未删未改。
- 本 worktree `data/videos/`：会话开始 5 个、结束仍 5 个（均为测试运行产生的 gitignored 占位小文件，未入库）。

### 1.7 下游消费方核对清单（实现要求 4）

grep 全仓（含 video-pipeline 侧）消费 `check_video_quality.py` 输出的方：

| 消费方 | 消费方式 | 是否按旧单口径解读 | 处置 |
|---|---|---|---|
| `video-pipeline/render_all_templates.py:71-79` | subprocess 调用（不带 --json），按 `returncode == 0 or returncode == 2` 判 `verified`，注释自述 "2 = skipped ML checks" | **是**——把「全 skip」也当 verified，属旧单口径 | 该文件在 `video-pipeline/`，**超出本卡白名单**（范围仅 scripts/check_video_quality.py + tests/video），未改动。本次刻意保持退出码语义不变（0 无失败 / 1 任一失败 / 2 全跳过），故其现有判定行为零回归；**请机审裁决**是否另卡把其 `verified` 对齐 `summary.pass_full` |
| `video-pipeline/generate_3_samples.py:126-131` | subprocess 调用后仅 `print(stdout)`，不解析、不判定 | 否（无口径依赖） | 无需改 |
| `video-pipeline/docs/research-notes/*.md`、`samples/README.md` | 文档引用 | 否 | 无需改 |
| `scripts/e2e_quality_verify.py` | 名义含"全部通过"字样，实为自递归 E2E 冒烟，不引用质量检查器 | 否 | 无需改 |
| `src/` 全目录 | grep 无 `check_video_quality` 引用，无 `--json` 解析方 | — | 无 |

## 2. 自测输出

### 2.1 本卡新增测试（验收标准 1）

```
$ python3 -m pytest tests/video/test_quality_dual_caliber.py -q -o addopts=""
.............................                                            [100%]
29 passed in 0.47s
EXIT=0
```

卡要求的 6 类用例齐全（实际 29 个测试函数，逐条对应）：
1. 全 pass → `pass_full is True` 且 `pass_partial is True` 且 `skip_names == []`（`TestAllPass`）
2. **1 项 `ok=None` → `pass_full is False`**（identity 断言）且 `skip_names` 含该项名（`TestSkipKillsFullCaliber`，含「9 技术参数全过+1 skip 仍不算全过」的病灶复现用例）
3. 1 项 `ok=False` → `pass_partial is False` 且 `pass_full is False`（`TestFailKillsBoth`，含 dict 形态跨视频展平）
4. 模型缺失 → `detail` 含 `model_cache_missing` 且**不含** `not installed`（`TestModelCacheMissingNotSilent`，并含「库未安装 vs 缓存缺失可区分」反向用例；缓存缺失用 `HF_HUB_CACHE` 指空目录实现，走被测函数真实判支，未 mock CLIP）
5. `summarize_quality` 六字段完整性（`TestSixFieldContract`，参数化 4 输入 + 类型断言，keys 集合 == {total, fail_count, skip_count, skip_names, pass_full, pass_partial}，缺一即红）
6. 正向回归：9 项技术参数阈值/判定逐一断言不漂移（`TestNineTechnicalParamsUnchanged`，含"无效时长按 fail 不降级为 skip"）

另加 CLI 接入测试（`TestCliWiring`）：`--json` 顶层 `summary` 六字段、`--report-md` 标题标口径且 pass_full=False 时禁「全部通过」、人读终端输出含汇总行。

### 2.2 定向 + 回归套件

| 命令 | 结果 | EXIT |
|---|---|---|
| `.venv/bin/python -m pytest tests/video/ -q`（默认 addopts） | **257 passed, 3 skipped** in 18.53s | 0 |
| `python3 -m pytest tests/content tests/core -q` | **160 passed** in 2.57s | 0 |
| `.venv/bin/python -m pytest tests/ -q`（全量） | 857 passed, 8 skipped, **2 failed** in 53.94s | 1 |

- 3 个 skip 均为 `test_bgm_tags.py` 的 `bgm_tags.json 不存在` 数据条件 skip，与本次改动无关。
- 全量 2 failed 在 `tests/openclaw/test_plugin_integration.py`，原因是 worktree 缺 gitignored 的 `openclaw-plugin/node_modules`（node 报 `ERR_MODULE_NOT_FOUND: Cannot find package 'typebox'`）。**基线证据**：同一测试在主仓（有 node_modules）跑 → 7 passed EXIT=0；本 worktree `ls openclaw-plugin/node_modules` → No such file or directory。属环境缺失，非本卡代码缺陷；本卡改动仅 2 个 Python 文件，与该 node 插件测试无 import 关系。
- 环境备注：系统 `python3` 有 sentence-transformers 2.7.0 无 sqlalchemy；仓库 `.venv` 反之。故定向测试用系统 python3 与 venv 各跑一遍均绿，全量用 venv。

### 2.3 lint

```
$ python3 -m ruff check scripts/check_video_quality.py tests/video/test_quality_dual_caliber.py
All checks passed!
```
