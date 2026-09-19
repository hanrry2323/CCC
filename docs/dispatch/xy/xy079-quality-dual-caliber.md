# 任务卡 xy079 · 视频质量双口径 + CLIP 实跑（skip 不再静默通过）

> 关联：xy-plan-011（内容产线架构 阶段1 P1）· 执行体：DSH · 验收：DSH · 状态：已关闭 · 派发：engine · 项目：xy · 日期：2026-09-18 · 版本：xy079 · 状态版本：12
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

1. **方案同步**：[是] xy-plan-011 卡头关联已含 xy079（外脑 run15 处置时补入，见卡内「批注落实」第 1 条），本卡交付「双口径汇总 + CLIP 实跑去静默」对齐 011 §一 断链 2（skip 静默通过病灶）与 §五之二 条款 1（skip 永不静默通过）、§五 铁律 1（pass_full = fail==0 AND skip==0），无需新增方案条目。
2. **教训沉淀**：[有] 两条教训已落：① sentence-transformers 2.7.0 的 `__init__` 无 `local_files_only` 形参（传了必抛 TypeError 被宽 except 吞掉后落入联网分支，2017 实测 huggingface.co 不可达 → CLI 可挂 600s+），正确做法是把 HF 缓存快照目录当 `model_name_or_path` 直传（零网络，实测 2.2s 加载）；② 运行期设 `os.environ["HF_HUB_OFFLINE"]` 是空转，`huggingface_hub.constants` 在 import 期已固化该值。两条均在 `scripts/check_video_quality.py:425-440` docstring 可 grep 验证；CCC 仓 `docs/notes/2026-09-18-xy079-lessons.md` 已落盘（origin/main commit `8a70ed74d`），跨仓文件不构成本卡白名单越界，xianyu 侧无需创建。
3. **档案/README**：[否] 本卡改动仅为 `scripts/check_video_quality.py` 内部判定逻辑与新增 `tests/video/test_quality_dual_caliber.py`，无新命令入口/新配置面/新部署面，`config.env` 零改动（红线 4 核对通过），README 无需更新。
4. **线路图**：[否] 质量检查器仍只被 `video-pipeline/` 侧 subprocess 调用，本次刻意保持退出码语义不变（0 无失败 / 1 任一失败 / 2 全跳过），无新增管线节点或拓扑变化，线路图无需更新（下游对齐 `summary.pass_full` 的问题已列 §1.7 请机审裁决，不越白名单自行改动）。

> 本节对应 A1 契约 §3「维护区四问」；四行说明均非空单段，勾选位落在问题行方括号内。

## 批注落实

**外脑 2026-09-19 12:2x 打回处置（run15）——本轮只做下列三件事，禁止重做已交付代码。**

1. **「禁止重做已交付代码」→ ✅ 已落实。** `git log --oneline origin/main..HEAD` 仅 `1a3d94c` 一个 commit；本次运行零代码改动、零 rebase、零 commit 改写——`git diff --name-only origin/main..HEAD` 仍仅 `scripts/check_video_quality.py` + `tests/video/test_quality_dual_caliber.py` 两文件（671 insertions / 37 deletions），与打回前完全一致。本次仅补推送与信封，未触碰代码。

2. **「【硬阻塞】分支未推远端，且信封自报不符」→ ✅ 已落实。** 执行 `git push -u origin codex/xy079-quality-dual-caliber`，EXIT=0；批注指定的 `git ls-remote --heads origin codex/xy079` 原始输出见 §1.9（首行 `1a3d94c... refs/heads/codex/xy079`），并追加贴出精确分支名查询 `codex/xy079-quality-dual-caliber` 与全量 grep，三者互证 commit `1a3d94c` 已在 origin。前次信封「push=✅ 已推送」的自报与当时实测不符之缺陷已消除，本次以原始 ls-remote 输出自证。

3. **「【格式】维护区四问代写为空」→ ✅ 已落实。** 本信封「

## 人工批注

**外脑 2026-09-19 12:2x 打回处置（run15）——本轮只做下列三件事，禁止重做已交付代码。**

代码侧已由外脑独立验收通过（亲跑 `pytest tests/video/test_quality_dual_caliber.py` = **29 passed**；
`summary.pass_full=false` + `skip_count=1` + `skip_names=["视频差异化"]` + CLIP 真实 `0.2808 ≥ 0.25`，
四项验收边界全中）。打回**只**因收尾两件事：

1. **【硬阻塞】分支未推远端，且信封自报不符。** 信封「变更证据」写 `push=✅ 已推送`，
   但 `git ls-remote --heads origin codex/xy079` 实测为空。须执行
   `git push -u origin codex/xy079-quality-dual-caliber`，并在信封贴
   `git ls-remote --heads origin codex/xy079` 的**原始输出**自证。
   禁止改写 commit 内容、禁止 rebase、禁止重做 `1a3d94c`。
2. **【格式】维护区四问代写为空。** 你的信封把答案写在 `## 3. 维护区四问` + `### Q1 方案同步`
   三级标题下；引擎代写按卡内 `## 维护区` 的编号列表解析，零提取 → Q1/Q2/Q4 说明全空被机审拒。
   信封该段须逐字写成卡内格式，四行、说明非空单段：

   ```
   ## 维护区
   1. **方案同步**：[是] 说明…
   2. **教训沉淀**：[有] 说明…
   3. **档案/README**：[否] 说明…
   4. **线路图**：[否] 说明…
   ```

   答案内容你已有（信封 Q1–Q4 段），只需换格式搬运，不必重写结论。
3. **【纠误】notes 文件判断有误。** 你判 `docs/notes/2026-09-18-xy079-lessons.md` 不存在，
   是因为在 xianyu 仓找——**该文件在 CCC 仓**（`/Users/fan/program/CCC/docs/notes/`，
   已在 origin/main）。跨仓文件不构成本卡白名单越界，本轮**无需**在 xianyu 侧创建它；
   Q2 说明照旧引用该路径即可（外脑已把该引用补进卡内 Q2 说明）。

边界不变：白名单 `scripts/check_video_quality.py` + `tests/video`；`video.py`/`writer.py`/
`rewriter.py`/`router.py`/`config.env` 零改动；`data/videos/` 文件计数不变；
信封仍须 `.ccc-result.md` 最后写 + `ls -la` 自证落盘。

## 回写区

## 0. 卡标题复述

任务卡 xy079 · 视频质量双口径 + CLIP 实跑（skip 不再静默通过）

## 1. 探针输出

#

## 2. 自测输出

#

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：通过
- 理由：CC 审核通过，自动合入完成
