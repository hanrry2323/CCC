# 任务卡 xy079 · 视频质量双口径 + CLIP 实跑（skip 不再静默通过）

> 关联：xy-plan-011（内容产线架构 阶段1 P1）· 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-18 · 版本：xy079 · 状态版本：1
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

1. **方案同步**：（执行体按信封第 3 段填写）
2. **教训沉淀**：（执行体按信封第 3 段填写）
3. **档案/README**：（执行体按信封第 3 段填写）
4. **线路图**：（执行体按信封第 3 段填写）

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区
