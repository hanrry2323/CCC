# 任务卡 xy067 · HyperFrames 真入口验收闭环（开发线 Build · 业务代码已在 main）

> 关联：xy-plan-008「视频高表现力二期」、xy-plan-009「前端展示台」 · 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-09 · 版本：xy067 · 状态版本：5
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标

xy064 的业务修复已全部合入 xianyu main（`f2ad113`，含 F1-F8：动态超时/workers/killpg/帧数 fail-fast/零残留/DataError 冒泡，35 项 video-pipeline 测试绿）。本卡完成「HyperFrames 真入口」的验收闭环（机审 PASS→关闭），不重复开发：

1. **独立核验**：确认 main 上 `video-pipeline/stages/scene/generator_hf.py` 动态超时、`_terminate_process_group`、`HyperFramesDataError` 冒泡等修复在位且与卡要求一致。
2. **端到端取证**：用当前配置（fps=30）重跑一次全量端到端渲染，`.ccc-result.md` 附原始 ffprobe 输出（codec/分辨率/帧率/时长）与 manifest 原文；无 fallback 字样；渲染后 `ps` 无孤儿进程。
3. **维护区四问**：以标准键名（①方案同步②教训沉淀③档案/README④线路图）如实作答；教训已落 `docs/lessons.md` Lesson 163/164（main 已含），②引用之。

## 实现要求

1. 不新增业务代码改动（main 已含全部修复）；仅验证+取证+如实回写。
2. 若发现 main 与卡验收标准不一致，如实记录并打回说明，不擅自改代码。

## 红线

1. 只改 xianyu 业务仓；不发布、不触碰 Cookie/外部账号、不启动 M7。
2. 不得删除既有产物；新跑使用唯一输出目录。
3. 结果如实记录；不得伪造 ffprobe/manifest 数据。
4. 不读取或输出凭据值。

## 范围

- `/Users/fan/program/apps/xianyu/video-pipeline/stages/scene/generator_hf.py`
- `/Users/fan/program/apps/xianyu/video-pipeline/tests/test_generator_hf.py`
- `/Users/fan/program/apps/xianyu/video-pipeline/config.json`
- `docs/lessons.md`

## 步骤

1. 确认 main 分支与代码在位；跑 `video-pipeline/tests/` 记录基线。
2. 用当前配置（fps=30）重跑全量端到端渲染，记录 ffprobe 原始输出与 manifest 原文。
3. 渲染后 `ps` 验证无孤儿进程。
4. 如实回写 `.ccc-result.md`：含独立核验结果、ffprobe/manifest 原文、测试输出、维护区四问（标准键名）、变更证据（commit/hash）。

## 验收标准

1. main 上 HyperFrames 真入口修复在位（动态超时/进程组清理/DataError 冒泡/帧数 fail-fast）。
2. 端到端成片 1080×1920、帧率 ≥24fps（当前配置 30fps），manifest 无 fallback 字样。
3. 渲染结束后无 npx/hyperframes/node 孤儿进程（ps 取证）。
4. `video-pipeline/tests/` 全部通过退出码 0。
5. 维护区四问以标准键名作答，教训引用 `docs/lessons.md` Lesson 163/164。
6. 无发布、无凭据泄露、无其他项目改动、无既有产物删除。
7. 不虚报：任何降级/缺失如实声明。

## 门禁

测试（视频组）：`/Users/fan/program/apps/xianyu/.venv/bin/pytest video-pipeline/tests/ -q`

## 回写要求

结果写入 `.ccc-result.md`，含独立核验、ffprobe/manifest 原文、测试输出、维护区四问、commit/hash、进程取证。

## 人工批注

无

## 回写区

## 0. 卡标题复述

任务卡 xy067 · HyperFrames 真入口验收闭环（开发线 Build · 业务代码已在 main）：不重复开发，仅完成 xy064 业务修复（f2ad113 合入 main）的验收闭环——独立核验 main 上 `video-pipeline/stages/scene/generator_hf.py` 修复在位且与卡要求一致、用当前配置（fps=30）重跑全量端到端渲染并附 ffprobe/manifest 原始取证、渲染后 ps 验证无孤儿进程、维护区四问以标准键名如实回写（教训引用 docs/lessons.md Lesson 163/164）。人工批注为占位（无）。

## 1. 探针输出

**独立核验（main f2ad113 基线，本地工作树分支 codex/xy067-hyperframes-acceptance = f2ad113，git diff f2ad113..HEAD 为空，无业务代码改动）**：

| 修复项 | 代码位置（generator_hf.py） | 核验结果 |
|---|---|---|
| 动态超时 | `_dynamic_timeout` L171-178：`max(120, ceil(per_frame×frames×1.5 + cold_start + 60))`，输入来自渲染前探针 | 在位 ✓（本次 e2e 复现：3.410×2436×1.5+3.821+60=12524.4 → timeout=12524，与日志一致） |
| 进程组清理 | `_terminate_process_group` L43-66：`start_new_session=True` + killpg(SIGTERM)→宽限 5s→killpg(SIGKILL)，组已空忽略 ProcessLookupError；`_run_hyperframes` L69-91 统一 finally 清理（成功/超时/OSError/非零退出各路径） | 在位 ✓ |
| DataError 冒泡 | L33 `HyperFramesDataError`；探针 fail-fast L148/156（帧数不足/全黑即抛）；渲染后校验 L457/473（成功退出码但帧数不足即抛）；冒泡分支 L406/441 先 `shutil.rmtree(hf_project_dir)` 零残留再 raise，独立于兜底 except（L369/412 的 `_fallback` 只处理非 DataError 路径） | 在位 ✓ |
| 帧数 fail-fast | L457/473 成功退出码但帧数≠期望即抛 DataError；探针 L148/156 同样 fail-fast | 在位 ✓ |
| 零残留 | 各冒泡/降级路径先 `shutil.rmtree(hf_project_dir)` 再返回（L409/415/439/443/446/456/472/508） | 在位 ✓ |

**测试覆盖核验**（`video-pipeline/tests/test_generator_hf.py`，18 用例）：进程组清理各 exit 路径（L18 子进程 kill / L28 超时 / L48 非零退出 / L79 OSError / L118 成功路径清孤儿）、动态超时与 bounded workers（L149/154）、探针全黑/部分帧/零帧 fail-fast（L161/189/242）、探针 DataError 冒泡不降级+零残留（L269/298/328）、scene.run 冒泡不吞（L401）。

**git 取证**：`git branch --contains f2ad113` → main 与当前分支均含；`docs/lessons.md` Lesson 163（L1628）、Lesson 164（L1640）在位，内容与上述代码一致（CCC 仓 lessons.md 亦有同源条目）。

## 2. 自测输出

**门禁测试**（`video-pipeline/tests/` 全量，命令：`/Users/fan/program/apps/xianyu/.venv/bin/pytest video-pipeline/tests/ -q`）：

```
============================== 35 passed in 2.36s ==============================
[exit code: 0]
```

**端到端渲染**（本会话重跑，唯一输出目录 `e2e-xy067/20260910-012900/video-pipeline/`，当前配置 fps=30；副本复制不触碰既有产物，既有 e2e 目录未删除）：

pipeline 输出原文关键行：
```
[01-script] ✅ 0.1s
01-script: 5 scenes, 80.0s, 218 chars
[02-scene] ✅ 705.4s
[02-scene] Config loaded. W=1080, H=1920, FPS=30
[generator_hf] Probe: cold=37.919s warm=34.098s cold_start=3.821s per_frame=3.410s frames=10
[generator_hf] Running HyperFrames CLI render: npx hyperframes@0.6.97 render --format=png-sequence --fps=30 ... (frames=2436, timeout=12524s, workers=4)
[generator_hf] Successfully captured 2436 frames (expected=2436). Mapping to standard pipeline schema...
[02-scene] 2436 frames → .../output/frames
[03-tts] ✅ 6.6s
[05-compose] ✅ 29.1s
04-compose: .../output/final.mp4 (81.2s, 49.5MB)
全部完成: 741.3s  GPU: cpu
```
- fallback 字样计数：`grep -o 'fallback\|HyperFrames unavailable' output/manifest.json | wc -l` = **0**（全程真 HyperFrames 入口，未降级 PIL）。
- 动态超时预算核验：3.410×2436×1.5 + 3.821 + 60 = 12524.4 → timeout=12524（与日志一致）。

**ffprobe 原始输出**（`ffprobe -v error -show_streams -show_format output/final.mp4`，关键字段原文）：
```
[STREAM index=0] codec_name=h264 profile=High
width=1080  height=1920  pix_fmt=yuv420p  field_order=progressive
r_frame_rate=30/1  avg_frame_rate=30/1  time_base=1/15360
duration_ts=1247232  duration=81.200000  bit_rate=4988237  nb_frames=2436
[STREAM index=1] codec_name=aac  sample_rate=24000  channels=1  duration=81.200000
[FORMAT] format_name=mov,mp4  duration=81.200000  size=51855556  probe_score=100
```

**manifest 原文**（`output/manifest.json` 节选 + `output/frames/scene_manifest.json` 全文）：
```json
"01-script": { "ok": true, "elapsed_sec": 0.1, "stdout": "01-script: 5 scenes, 80.0s, 218 chars\n", "stderr": "" }
"02-scene": { "ok": true, "elapsed_sec": 705.4, "stdout": "...[generator_hf] Successfully captured 2436 frames (expected=2436)...", "stderr": "" }
"03-tts": { "ok": true, "elapsed_sec": 6.6, "stdout": "...audio.mp3, srt=...subs.srt, 57.408s", "stderr": "Trying voice candidate: zh-CN-YunxiNeural\nVoice generation success using voice: zh-CN-YunxiNeural" }
"05-compose": { "ok": true, "elapsed_sec": 29.1, "stdout": "...[04-compose] Reconstructed 2436 frames from manifest...final.mp4 (81.2s, 49.5MB)", "stderr": "" }
```
```json
// output/frames/scene_manifest.json（原文）
{ "0": {"scene": 0, "frames": 513, "duration": 17.1},
  "1": {"scene": 1, "frames": 462, "duration": 15.4},
  "2": {"scene": 2, "frames": 519, "duration": 17.3},
  "3": {"scene": 3, "frames": 468, "duration": 15.6},
  "4": {"scene": 4, "frames": 438, "duration": 14.6} }
```
帧数核验：场景帧 513+462+519+468+438=2400 + 过渡帧 4×9=36 = **2436**，与 ffprobe nb_frames=2436、`ls output/frames/*.png | wc -l`=2436 一致。

**孤儿进程取证（渲染完成后 ps）**：
- `ps aux | grep -E 'npx|hyperframes' | grep -v grep | grep -v dsh` → **0** 个（仅命中本执行体 dsh 自身 node PID 5184，非渲染进程）。
- `ps aux | grep -E 'chrome-headless-shell.*hyperframes'` → **0** 个；`ps aux | grep '/Users/fan/.cache/hyperframes/'` → **0** 个。
- 结论：渲染结束后无 npx/hyperframes/node 孤儿进程，无 HyperFrames 派生 chrome 残留。

## 维护区

1. **方案同步**：[是] 本卡为 xy064 修复（f2ad113）的验收闭环，HyperFrames 真入口方案（动态超时/进程组清理/DataError 冒泡/帧数 fail-fast）已在 main 全部在位且本次 e2e 实证通过；关联方案 xy-plan-008 状态「部分执行」且关联卡含 xy067，无新方案变更。
2. **教训沉淀**：[有] 教训已随 xy064 落 docs/lessons.md Lesson 163（固定超时必挂/--fps 显式/low-memory 与多 worker 互斥/进程组清理）与 Lesson 164（显式帧率/动态预算依赖真实探针），main 已含，本卡直接引用未重复新增。
3. **档案/README**：[否] 无档案/README 变更需求；video-pipeline README 已覆盖 pipeline 用法，本卡无新 API/命令。
4. **线路图**：[否] 无线路图变更；本卡为验收闭环，不引入新路线项。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：完成钩子：维护区只找到 0/4 问
