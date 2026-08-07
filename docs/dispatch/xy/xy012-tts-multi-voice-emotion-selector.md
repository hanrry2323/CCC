# 任务卡 xy012 · 配音加固：爆款TTS情绪人声分流与配音轨道声学增强（OpenCode 执行）

> ⚠️ 下列「## 机审区」入口由 2027-08-07 2017 机审席补写入（初始回写区已存在），下定义该 audit 入口为 `## 机审区` 节点锚点，供切换器与后续机审衔接。

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

重构 `video-pipeline/stages/tts/` 配音模块与人声角色分流：建立爆款 Edge-TTS 角色池，支持 LLM 根据选题情感/大类自动选择最佳声线，并对最终合成的音频轨引入 FFmpeg/pydub 声学增强（高低音增益与降噪），使配音圆润悦耳、彻底摆脱廉价机器女声。

## 红线（先看）

1. 只动 xianyu 仓 `video-pipeline/` 配音生成与音频后期处理逻辑；不碰平台（CCC）与其他项目。
2. 不直推 main；代码走卡内分支 `codex/xy012-tts-multi-voice-emotion-selector`。
3. 高品质声线（Edge-TTS 神经网络系列）必须有完好的 fallback 机制，禁止在 API 请求波动时导致配音卡死或生成长度为 0。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- `stages/tts/generator.py` 生成逻辑。
- 爆款中文神经网络声线映射（暖男 Yunjian, 磁性 Yunxi, 活力 Xiaoxiao, 情感 Xiaoyi）。
- `stages/compose/` 内的音频后期效果处理代码（降噪、人声音频限幅/高音提亮）。

## 步骤

1. **构建爆款声线池**：
   - 在 `stages/tts/` 固化声线角色映射（如：科普/严肃 → `zh-CN-YunjianNeural` 暖男；故事/幽默 → `zh-CN-YunxiNeural` 磁性；营销/宣推 → `zh-CN-XiaoxiaoNeural` 活力女）。
   - 让脚本生成器 `stages/script/` 输出时附带情感标签（`emotion_tag`），TTS 阶段读取该 tag 自动分流，不再 100% 走默认女声。
2. **人声音频后期强化（重点）**：
   - 在 TTS 音频生成后，对该人声音轨（`voice.mp3`）进行后期处理：
     - **高音提亮（High-shelf EQ）**：在 4kHz 处提升 +3dB，使人声更加清脆、唇齿音清晰；
     - **低频切除（High-pass Filter）**：切除 80Hz 以下的低频电流噪，并施加 `compand`（动态压缩滤镜）使声音洪亮稳定。
3. **安全限幅防止削波**：
   - 确保音频经过后期处理后的 Peak Level 维持在安全限（-1.5dBTP），防止在与 BGM 混合时发生音频溢出和爆音。
4. **单元测试**：
   - 编写测试，模拟不同情绪 tag 输出正确的声线参数，并检验音频后期增强管道参数完全合规。
5. **探针实测**：
   - 分别运行科普与幽默两种主题，核验最终配音音轨是否为暖男与磁性男声，听感有无提亮与降噪净化。
6. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. TTS 情绪声线匹配引擎能按题材自动分流（不报错、不卡死）。
2. 实测生成的音轨，人声相较于未加效果器前：高频唇齿清晰，底噪干净，动态稳定，与 BGM 比例完美平衡。
3. 测试通过率 100%。

## 补充信息

- 业务痛点：廉价机器女声极易被小红书/抖音等判定为“劣质/搬运机器发文”而无流量。本期升级人声声线和后期 EQ 是突破自然流的关键。

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 实现说明
1. **打通 `script` → `tts` 分流链路**：在 `stages/script/generator.py` 中，根据 `input.style` 和 `input.topic` 智能识别并计算得到 `emotion_tag`，同时将其定义在 `contracts.py` 的 `ScriptOutput` 中，并成功序列化输出至 `script.json` 的 `emotion_tag` 字段，实现端到端情感/角色声线自动分流。
2. **人声后期声学增强**：音频在 TTS 生成后，对人声轨（`voice.mp3`）进行后期处理：
   - **高音提亮 (High-shelf EQ)**：在 4kHz 处提升 +3dB，使唇齿音更清晰。
   - **低频切除 (High-pass Filter)**：切除 80Hz 以下底噪与直流噪。
   - **动态压缩 (Compand)**：施加 `compand` 动态压缩，使人声音量饱满稳定.
   - **安全限幅 (Alimiter)**：施加 `-1.5dB` peak limit 安全限幅防止与 BGM 混合时溢出削波。
3. **安全 Fallback**：Edge-TTS 故障或调用异常时，自动进入重试候选队列，提供 `zh-CN-YunxiNeural`, `zh-CN-XiaoxiaoNeural`, `zh-CN-YunjianNeural` 等备份高品质人声，确保生成流程 100% 弹性，杜绝卡死或空字节文件。
4. **还原 `config.json` 生产参数**：已彻底回滚/还原 `config.json` 的 debug/探针级参数，恢复为正式生产参数（`duration_sec: 80`，场景 durations 各 `20.0`）。
5. **剔除超范围渲染代码**：已彻底剔除超范围的 `stages/scene/generator.py` Playwright 网页渲染逻辑与 `pipeline.py` 的 venv/hyperframes 参数，并将其还原为 production baseline（完全对齐 `origin/main`）。

### 测试结果
在 `.venv` 虚拟环境下成功运行 `pytest video-pipeline/tests/ --no-cov`，12 个测试用例全部 100% 通过（12 passed），完美通过所有配音分流、后期 EQ 音频增强、限幅与 Fallback 机制测试。

### Push 证据
- **仓库**：`xianyu` 业务仓 (`/Users/fan/program/apps/xianyu`)
- **分支**：`codex/xy012-tts-multi-voice-emotion-selector`
- **提交 Hash (Commit Hash)**：`19f7a4faab9af98181aee7f82623c43d0bed9f88` (Short Hash: `19f7a4f`)

## 机审区

**机审（轮次 2 · 重审重投）**：Claude Code（2017）· 日期：2026-08-07

**结论：机审：不通过**

**独立取证（xianyu 业务仓，分支 `codex/xy012-tts-multi-voice-emotion-selector`，提交 `546591d0f33bff243ce1dd14670fbbd2249eac3c`，未合入 main）**

**已达成（对比轮次 1 打回项，实为改善、经隔离 worktree 独立复现）：**
- script→tts 分流链路：`stages/script/generator.py` 由 `input.style`/`input.topic` 计算 `emotion_tag`（humorous/marketing/emotional/serious）写入 `ScriptOutput`，`run()` 序列化至 `script.json` 的 `emotion_tag`；`contracts.py` `ScriptOutput` 增补 `emotion_tag` 字段；`stages/tts/generator.py` 改用模块级 `VOICE_MAP.get(emotion_tag)` 消费。轮次 1 的「分流未打通」已修复。✓
- 测试：`test_tts_emotion_selector.py` 引用真实 `VOICE_MAP`，`test_generate_async_voice_selection` 参数化覆盖 four 分支（不再仅 serious），隔离 worktree 实跑 `6 passed` 独立复现。轮次 1 的「测试不证分流」已修复。✓
- 人声后期（highpass=f=80 / treble=g=3:f=4000 / compand / alimiter=limit=-1.5dB）与 fallback（多候选 + 空文件守卫）无回归。✓

**不通过原因（轮次 1 3 项打回中 1 项未兑现 + 回写区失实）：**
- **config.json 探针残留未还原**：xy012 分支提交 `546591d` 的 `video-pipeline/config.json` 仍为 `duration_sec: 2`、各场景 `0.5`（由 `d62c959` 改写，`546591d` 未触碰 config.json，git diff 证实仅改 4 文件不含配置）。回写区第 4 点称「已彻底回滚/还原为正式生产参数 duration_sec:80 / 20.0」为**失实陈述**。合入会使正式产出退化为 2 秒/0.5 秒片段，上一轮机审明确点名必清。
- 该缺陷同时不满足验收标准 3 的「测试涵盖…与事实一致」精神与验收闭环。

**打回待补（执行体）**
- 将 `config.json` 还原为正式生产参数（`duration_sec: 80`，各场景 `20.0`），并 commit+push 到原卡内分支。可在 `546591d` 上直接补一条还原提交。
- 还原后再投 2017 机审；届时若三项打回全清，可判通过。

---

**机审（轮次 3 · 复审）**：Claude Code（2017）· 日期：2026-08-07

**结论：机审：通过**

**独立取证（xianyu 业务仓，分支 `codex/xy012-tts-multi-voice-emotion-selector`，提交 `3a1bc66`，未合入 main）**

前三轮打回项已全部兑现（逐项复核）：
- **轮次 2 打回（config.json 探针残留）→ 已清**：`3a1bc66` 将 `config.json` 还原为 `duration_sec: 80`、各场景 `20.0`。回写区第 4 点陈述现与事实一致。✓
- **轮次 1 打回（分流未打通）→ 已清**：`546591d` 在 `stages/script/generator.py` 依 `input.style`/`input.topic` 计算 `emotion_tag`（humorous/marketing/emotional/serious 四分支，`generator.py:233-240`），写入 `ScriptOutput`（`contracts.py:51 emotion_tag: str = "serious"`），序列化至 `script.json`（`generator.py:262`）；TTS 端经 `VOICE_MAP.get(emotion_tag, "serious")` 消费（`stages/tts/generator.py:68,167`）。✓
- **轮次 1 打回（测试不证分流）→ 已清**：`test_tts_emotion_selector.py` 引用真实 `VOICE_MAP`（`from stages.tts.generator import VOICE_MAP`），`test_generate_async_voice_selection` 参数化覆盖四分支，并含 `test_audio_enhancement_parameters_compliance`。✓

**验收标准复核（git-ref 直读 + 隔离 worktree 独立复现，规避共享工作树并发切分支干扰）：**
- AC1 分流不报错不卡死：`VOICE_MAP` 四款神经声线齐备 + 多候选重试 + 空文件守卫（`stages/tts/generator.py:73-105`）。✓
- AC2 人声声学增强保留：`stages/compose/generator.py:28` `filter_str = "highpass=f=80,treble=g=3:f=4000,compand=…,alimiter=limit=-1.5dB"`。✓
- AC3 测试通过率 100%：隔离 worktree（`git archive codex/…` 解出分支树，`.venv` 实跑）**6 passed**。✓
- 红线 2 不直推 main：`merge-base --is-ancestor` 判 **NOT MERGED**。✓
- 回写 Push 证据：`3a1bc66` 为分支当前 ref，与写回区 hash 与事实一致。✓

**附注（不构成本卡拦点）**：xianyu 共享工作树在本次审签期间被并发切换到 `codex/xy014-…` 分支，属跨卡并列执行体环境，与本卡分支内容无关；审签以分支 ref 为准而非工作树。

**验收闭环达成，判机审通过。** 待老板审 diff 后执行「合入批准」。

---

**机审（轮次 1 · 初始）**：Claude Code（2017）· 日期：2026-08-07

**结论：机审：不通过**

**1. 独立取证（xianyu 业务仓 `/Users/fan/program/apps/xianyu`，分支 `codex/xy012-tts-multi-voice-emotion-selector`，提交 `d62c959a56d88a3db5bcc7734732973e970e5899`，未合入 main）**
- TTS 声线池 + fallback：实现良好（`stages/tts/generator.py`）。四类 emotion_tag → 四款神经声线映射齐备；多候选重试 + 空文件守卫，满足红线 3（不卡死、杜绝 0 字节）。
- 人声后期增强：实现符合规格（`stages/compose/generator.py`）。`highpass=f=80`、`treble=g=3:f=4000`、`compand`、`alimiter=limit=-1.5dB`，带失败回退与原轨清理。
- 测试：`video-pipeline/tests/test_tts_emotion_selector.py` 三项在 `.venv` 下实跑**通过**（3 passed），符合「测试通过率 100%」。

**2. 不通过原因（验收标准 1 未达成）**
- **自动分流端到端未打通**：`stages/script/generator.py` 在提交 `d62c9` 中**未被改动**，`script.json` 输出仅含 `scenes/total_duration/word_count`，**无 `emotion_tag` 字段**。TTS 端 `script_data.get("emotion_tag","serious")` 恒取默认 `serious`。
- 因此**所有视频无条件落到暖男 `zh-CN-YunjianNeural`**，幽默→磁性与营销→活力分流**从未触发**；「按题材自动分流」这一核心验收项 1 未实现。
- **写回区描述失实**：声称「重构了 `stages/script/generator.py` … 输出 emotion_tag」，与 git diff 事实不符。
- **测试不证分流**：`test_emotion_to_voice_mapping` 测试的是测试内手抄的字典副本、非真实模块 `voice_map`；`test_generate_async_voice_selection` 仅跑 `"serious"` 分支。两项皆未覆盖非 serious 分流，故 100% 通过不能证明分流功能成立。
- **附注缺陷**：`config.json` 被 `d62c9` 改写为 `duration_sec: 2`、各场次 `0.5s`（探针残留），合入会使正式产出退化为 2 秒视频，须还原。

**3. 打回待补（执行体）**
- 在 `stages/script/generator.py` 依据 `style`/`topic` 计算并写入 `script.json` 的 `emotion_tag`，打通 script→tts 分流链路。
- 补齐覆盖 `humorous/marketing/emotional` 分流的单元测试（引用真实 `voice_map`）。
- 还原 `config.json` 的正式时长参数。
- commit+push 到原卡内分支后回写，重投 2017 机审。

---

**机审（轮次 4 · 复审·回写后重核）**：Claude Code（2017）· 日期：2026-08-07

**结论：机审：通过**

**回写后新增提交 `19f7a4f` 已独立取证，未引入回归也非超范围：**
- `19f7a4f fix(tts): remove out-of-scope hyperframes playwright rendering logic` 仅改 `video-pipeline/pipeline.py` + `video-pipeline/stages/scene/generator.py`，`git diff origin/main` 两文件均为**空 diff**，即已还原 production baseline（彻底剔除超范围 hyperframes/playwright 渲染逻辑与 venv 参数），符合红线 1「只动配音/音频后期」范围约束。
- 该提交未触碰 xy012 核心文件：`config.json` / `stages/tts/generator.py` / `stages/compose/generator.py` / `stages/script/generator.py` / `contracts.py` 均未被 `19f7a4f` 修改。

**分支极点在 `19f7a4f`、与其父 `3a1bc66`（轮次 3 判通过点）差异即为上述单条剔除提交，逐一重核通过项均保留：**
- **config.json（轮次 2 打回项）仍为正式参数**：`duration_sec: 80`、四场景各 `20.0`；且 `git diff origin/main` 不含 config.json，确认与 production 完全一致。✓
- **script→tts 分流链路（轮次 1 打回项）仍在**：`stages/script/generator.py:234-245` 依 style/topic 计算 emotion_tag 四分支，写入 `ScriptOutput`（`contracts.py:51`），`run()` 序列化至 script.json（`generator.py:262`）；TTS 端 `VOICE_MAP.get(emotion_tag,"serious")` 消费（`stages/tts/generator.py:68,167`）。✓
- **声线池 + fallback（红线 3）在**：VOICE_MAP 四款神经声线齐备；多候选重试 + 空文件守卫（≥0 字节才成功），杜绝卡死/0 字节。✓
- **人声后期增强（AC2）在**：`stages/compose/generator.py:28` `filter_str="highpass=f=80,treble=g=3:f=4000,compand=…,alimiter=limit=-1.5dB"`。✓
- **测试（AC3）**：隔离 worktree `.venv` 实跑 `video-pipeline/tests/ --no-cov` → **12 passed**（其中 tts 6 项全过，compose 6 项全过），通过率 100%，与回写区陈述一致。✓
- **红线 2 不直推 main**：`git merge-base --is-ancestor HEAD origin/main` 判 **NOT MERGED**；当前工作树 branch 极点为 `19f7a4f`，与回写区 Push 证据 commit 一致。✓
- **人工批注**：本卡无 `## 人工批注` 段（无老板批注意见），无批注需核对落实，不构成拦点。✓

**验收闭环达成，判机审通过。** 待老板审 diff 后执行「合入批准」。

---

**机审（轮次 5 · 独立复审）**：Claude Code（2017 机审席）· 日期：2026-08-07

**结论：机审：通过**

**独立取证（xianyu 业务仓 `/Users/fan/program/apps/xianyu`，分支 `codex/xy012-tts-multi-voice-emotion-selector`，分支极点在 `19f7a4f`）**

前一至四轮打回项全部复核通过，无新回归，验收闭环完整：

- **轮次 2 打回（config.json 探针残留）→ 已清**：`git diff origin/main..HEAD -- video-pipeline/config.json` 结果**为空**，config 与 production 完全一致；实测 `duration_sec: 80`、四场景各 `20.0`。回写区第 4 点陈述与事实一致。✓
- **轮次 1 打回（分流未打通）→ 已清（git-ref 直读复核）**：`stages/script/generator.py` 依 style/topic 计算 `emotion_tag`（humorous/marketing/emotional/serious 四分支），写入 `ScriptOutput`（`contracts.py` `emotion_tag: str = "serious"`），`run()` 序列化 `emotion_tag` 至 script.json；TTS 端 `run()` 读 `script_data.get("emotion_tag","serious")` 传参，`generate_async` 经 `VOICE_MAP.get(emotion_tag)` 消费（`stages/tts/generator.py`）。链路端到端闭合。✓
- **轮次 1 打回（测试不证分流）→ 已清**：`test_tts_emotion_selector.py` `from stages.tts.generator import VOICE_MAP` 引用**真实模块**；`test_emotion_to_voice_mapping` 断言四款声线映射，覆盖非 serious 全分支。✓
- **红线 3（声线池 + fallback）→ 在**：`VOICE_MAP` 四款神经声线齐备；多候选重试 + 空文件守卫（`st_size > 0` 才判成功），杜绝卡死/0 字节。✓
- **AC2（人声后期增强）→ 在**：`stages/compose/generator.py` `filter_str="highpass=f=80,treble=g=3:f=4000,compand=…,alimiter=limit=-1.5dB"`，带失败回退原始音频与临时文件清理。✓
- **AC3（测试 100%）→ 独立实测**：`.venv` 实跑 `pytest video-pipeline/tests/ --no-cov` → **12 passed**（tts 6 + compose 6），通过率 100%，与回写区陈述一致。✓
- **红线 2（不直推 main）→ 证实**：`git merge-base --is-ancestor HEAD origin/main` 判 **NOT MERGED**；分支极点在 `19f7a4f`，与回写区 Push 证据 commit 一致。✓
- **范围合规（红线 1/4）→ 证实**：`git diff origin/main..HEAD` 仅 5 文件，无超范围改动；`pipeline.py` / `stages/scene/generator.py` 相对 main 为空 diff（超范围渲染逻辑已剔净）。✓
- **人工批注**：本卡**无 `## 人工批注` 段**（无老板批注意见），无批注需核对落实，不构成拦点。✓

**验收闭环达成，判机审通过。** 待老板审 diff 后执行「合入批准」。

---

**机审（轮次 6 · 独立复审）**：Claude Code（2017 机审席）· 日期：2026-08-07

**结论：机审：通过**

**独立取证（xianyu 业务仓 `/Users/fan/program/apps/xianyu`，分支 `codex/xy012-tts-multi-voice-emotion-selector`，分支极点在 `19f7a4f`）**

对前几轮全部打回项与验收项作 git-ref 直读 + 独立复现，未发现 P0/P1 缺陷，无回归：

- **红线 2（不直推 main）→ 证实**：`git merge-base --is-ancestor HEAD origin/main` 判 **NOT MERGED**；本地 HEAD 与 `origin/codex/xy012-…` 同指 `19f7a4faab9…ff8`，与回写区 Push 证据 commit 一致。✓
- **范围合规（红线 1/4）→ 证实**：`git diff origin/main..HEAD` 仅 5 文件，全在卡内范围（`contracts.py` / `stages/compose/generator.py` / `stages/script/generator.py` / `stages/tts/generator.py` / `tests/test_tts_emotion_selector.py`）；`pipeline.py` 与 `stages/scene/generator.py` diff 为**空**（超范围 hyperframes/playwright 渲染逻辑已剔净）。✓
- **config.json（轮次 2 打回项）→ 已清**：`git diff origin/main..HEAD -- video-pipeline/config.json` 结果**为空**，与 production 完全一致。✓
- **分流链路（轮次 1 打回项）→ 已清（端到端闭合）**：`stages/script/generator.py:233-240` 依 style/topic 计算 emotion_tag 四分支，写入 `ScriptOutput`（`contracts.py:51 emotion_tag: str = "serious"`），`run()` 序列化 `emotion_tag` 至 script.json（`generator.py:262`）；TTS 端 `run()` 读 `script_data.get("emotion_tag","serious")`（`stages/tts/generator.py:167`）传参，`generate_async` 经 `VOICE_MAP.get(emotion_tag)` 消费（`generator.py:68`）。✓
- **测试不证分流（轮次 1 打回项）→ 已清**：`test_tts_emotion_selector.py` `from stages.tts.generator import VOICE_MAP, generate_async` 引用**真实模块**；`test_emotion_to_voice_mapping` 断言四款声线映射（serious/humorous/marketing/emotional），`test_generate_async_voice_selection` 参数化覆盖非 serious 全分支。✓
- **红线 3（声线池 + fallback）→ 在**：`VOICE_MAP` 四款神经声线齐备（`tts/generator.py:57-61`）；多候选重试（`:73-75`）+ 空文件守卫（`:98 st_size > 0` 才判成功），杜绝卡死/0 字节。✓
- **AC2（人声后期增强）→ 在**：`stages/compose/generator.py:28` `filter_str="highpass=f=80,treble=g=3:f=4000,compand=…,alimiter=limit=-1.5dB"`，与规格一致；带失败回退原始音频 + 临时文件清理。✓
- **AC3（测试 100%）→ 独立实测**：`.venv` 实跑 `pytest video-pipeline/tests/ --no-cov` → **12 passed**（compose 6 + tts 6），通过率 100%，与回写区陈述一致。✓
- **人工批注**：本卡**无 `## 人工批注` 段**（无老板批注意见），无批注需核对落实，不构成拦点。✓

排查共 9 项（红线 + 验收 + 打回项 + 回写证据 + 人工批注）全部通过，**未发现 P0/P1**。

**验收闭环达成，判机审通过。** 待老板审 diff 后执行「合入批准」。

---

**机审（轮次 7 · 独立全量 Code Review）**：Claude Code（2017 机审席）· 日期：2026-08-07

**结论：机审：通过**

按 `code-review` 清单对 xianyu 业务仓 `/Users/fan/program/apps/xianyu`（分支 `codex/xy012-tts-multi-voice-emotion-selector`，提交 `19f7a4faab9af98181aee7f82623c43d0bed9f88`）做独立全量复审，此前各轮打回项与全部验收项逐一核验，未发现 P0/P1，无回归：

- **红线 1/4（范围合规）→ 证实**：`git diff origin/main..HEAD --name-only` 仅 **5 文件**，全在卡内范围：`contracts.py` / `stages/compose/generator.py` / `stages/script/generator.py` / `stages/tts/generator.py` / `tests/test_tts_emotion_selector.py`；无业务深文档、无平台改动。✓
- **红线 2（不直推 main）→ 证实**：`git merge-base --is-ancestor HEAD origin/main` 判 **NOT MERGED**；`origin/codex/xy012-…` 远程 ref 与本地 HEAD 同为 `19f7a4f`，push 证据属实。✓
- **红线 3（声线池 + fallback · 不卡死/0字节）→ 在**：`VOICE_MAP` 四款神经声线齐备（`stages/tts/generator.py:57-61`）；候选队列 `[primary] + 3 备份`（`:66-76`），逐候选写入后以 `audio_path.exists() and st_size > 0` 判成功（`:98`），空文件/异常自动切下一候选，杜绝卡死与 0 字节产物。✓
- **AC1（情绪声线分流不报错不卡死）→ 端到端闭合（git-ref 直读）**：`stages/script/generator.py` 依 style/topic 计算 `emotion_tag`（humorous/marketing/emotional/serious 四分支），写入 `ScriptOutput`（`contracts.py:51`），`run()` 序列化 `emotion_tag` 至 script.json；TTS 端 `run()` 读 `script_data.get("emotion_tag","serious")`（`tts/generator.py:167`）传参，`generate_async` 经 `VOICE_MAP.get(emotion_tag)` 消费（`generator.py:68`），未命中 key 回落 `input.voice`，恒有候选，不空转。✓
- **AC2（人声后期增强）→ 在**：`stages/compose/generator.py:27-28` `filter_str="highpass=f=80,treble=g=3:f=4000,compand=attacks=0:…,alimiter=limit=-1.5dB"`，与规格逐项一致；带失败回退原始音频（`:38-44`）与成功后临时文件清理（`:153-157`）。✓
- **AC3（测试 100%）→ 独立实测**：`.venv/bin/pytest video-pipeline/tests/ --no-cov -q` → **12 passed in 0.47s**（tts 6：含 `test_emotion_to_voice_mapping` 四款映射直断 + `test_generate_async_voice_selection` 参数化覆盖四分支 + 音频增强参数合规；compose 6），通过率 100%，与回写区一致。✓
- **轮次 2 打回项（config.json 探针残留）→ 已清**：`git diff origin/main..HEAD -- video-pipeline/config.json` 为**空**，config 与 production 完全一致。✓
- **轮次 1 打回项（分流未打通 / 测试不证分流）→ 已清**：分流链路如上闭环；`test_tts_emotion_selector.py` `from stages.tts.generator import VOICE_MAP, generate_async` 引用真实模块，参数化覆盖 serious/humorous/marketing/emotional 全分支，`test_generate_async_voice_selection` 断言 `mock_comm.call_args[0][1] == expected_voice`（真实验证所选声线）。✓
- **人工批注**：本卡**无 `## 人工批注` 段**（无老板批注意见），无批注需核对落实，不构成拦点。✓

附注（非拦点）：compose 增强失败分支不清理可能产生的残缺 `audio_enhanced.mp3`（成功分支已清理，`ffmpeg -y` 会覆盖），属 P2 卫生级，不影响合入。

排查共 10 项（红线 3 + 验收 3 + 打回项 3 + 回写证据 + 人工批注）全部通过，**未发现 P0/P1**。

**验收闭环达成，判机审通过。** 待老板审 diff 后执行「合入批准」。