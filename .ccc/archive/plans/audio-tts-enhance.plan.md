# Plan: audio-tts-enhance — TTS 语音增强：SSML break/pitch/rate 注入 + voice 调优

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

### 核心源码分析
- **`src/xianyu/video/tts.py`**（96 行）— 生产 TTS 模块，当前仅用 `edge_tts.Communicate(text, voice).save()` 最简单调用，**无 SSML、无 rate、无 pitch、无 break 注入**。只有 3 个 Chinese voice 的硬编码列表。`generate_tts()` 仅接受 `(text, output_path, voice=)` 参数
- **`src/xianyu/video/__init__.py`** — 从 `.tts` 导出 `generate_tts`、`generate_tts_safe`、`get_available_voices`
- **`src/xianyu/content/video.py`** — 编排器：`execute()` 从 `ctx` 读参 → `process()` → `_generate_tts(scenes)` 内部 hardcode 调用 `generate_tts_safe(full_text, str(output_path))`，**没有任何 voice/rate/pitch 参数通道**。`ctx` 中不存在任何 TTS 配置项
- **`tests/video/test_tts.py`** — 9 个测试，全部 mock `edge_tts.Communicate` 或 `generate_tts`。**无 SSML 测试、无 rate/pitch 参数测试**
- **`tests/content/test_tts.py`** — 测试 content 层的 mock worker，与本任务无关

### 关键实现注意事项
- **edge-tts SSML 模式**：当 text 以 `<speak>` 开头时自动进入 SSML 模式。**SSML 模式下 Communicate 构造函数的 `rate=` / `pitch=` 参数被忽略**——rate/pitch 必须嵌入 SSML 的 `<prosody>` 标签内
- **`video-pipeline/`** 是独立子项目，不在本任务范围内
- 整项目零 SSML 使用

### 待改动点
- `src/xianyu/video/tts.py`：核心 TTS 模块，需要添加 SSML 构建 + break 注入 + rate/pitch 嵌入 prosody
- `src/xianyu/video/__init__.py`：导出新增常量
- `src/xianyu/content/video.py`：`_generate_tts()` → `process()` → `execute()` 参数透传链
- `tests/video/test_tts.py`：新增 SSML/rate/pitch/break 测试

---

## 范围

- **目标**：向 edge-tts 注入 SSML `<break>` + `<prosody rate/pitch>` 实现 TTS 语音自然度提升，并将 voice/rate/pitch/break 参数通过编排器透传到执行
- **只改文件**：
  - `src/xianyu/video/tts.py`
  - `src/xianyu/video/__init__.py`
  - `src/xianyu/content/video.py`
  - `tests/video/test_tts.py`
- **不改文件**：`video-pipeline/` 下任何文件、`content/tts.py`、`bridge/`、任何配置/依赖文件
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：TTS 核心模块 SSML + rate/pitch + break 注入 + voice 扩充

### 做什么

在 `video/tts.py` 中实现 SSML 结构化语音包装，使 TTS 输出具有自然停顿（句间 break）、音调/语速控制能力，并扩充可信 voice 列表。

**为什么需要 SSML（非 edge-tts 构造参数）：**
- edge-tts 的 `rate=` / `pitch=` 构造参数仅对纯文本模式生效，SSML 模式下被忽略
- `<break/>` 是 SSML 独有元素，构造参数不提供
- 当文本以 `<speak>` 开头时 edge-tts 自动进入 SSML 模式，rate/pitch 须嵌入 `<prosody>` 标签

**预期效果：** 生成的 TTS MP3 在句与句之间有 300ms 自然停顿，听感不再「句子连读挤在一起」；rate/pitch 参数可调以适配不同内容风格（快语速/慢语速/高音/低音）。

### 怎么做

**`src/xianyu/video/tts.py`：**

1. **新增 SSML 构建函数（插入在 `_CHINESE_VOICES` 常量和 `get_available_voices` 之间，约第 28 行）**：
   ```python
   import re

   DEFAULT_BREAK_MS: Final[int] = 300
   DEFAULT_RATE: Final[str] = "+0%"
   DEFAULT_PITCH: Final[str] = "+0Hz"

   def _build_ssml(
       text: str,
       *,
       rate: str = "+0%",
       pitch: str = "+0Hz",
       break_ms: int = 300,
   ) -> str:
       """Wrap text in SSML with prosody rate/pitch and sentence-break injection.

       Args:
           text: Plain text (may contain 。！？etc.)
           rate: Speaking rate string, e.g. "+10%", "-5%".
           pitch: Speaking pitch string, e.g. "+0Hz", "-20Hz".
           break_ms: Millisecond pause after each sentence-ending punctuation
                     (。！？). Set to 0 to disable break injection.

       Returns:
           SSML string ready for edge_tts.Communicate().
       """
       if break_ms > 0:
           text = re.sub(r'([。！？.!?])', rf'\1<break time="{break_ms}ms"/>', text)
       return f'<speak><prosody rate="{rate}" pitch="{pitch}">{text}</prosody></speak>'
   ```

2. **扩充 `_CHINESE_VOICES`（第 18-22 行）**：追加 `zh-CN-XiaomoNeural`（温暖讲故事）和 `zh-CN-XiaoshuangNeural`（甜美轻松）。从 3 个扩到 5 个：
   ```python
   _CHINESE_VOICES: Final[list[str]] = [
       "zh-CN-XiaoxiaoNeural",     # 女声，亲和
       "zh-CN-YunxiNeural",        # 男声，年轻
       "zh-CN-XiaohanNeural",      # 女声，温暖
       "zh-CN-XiaomoNeural",       # 女声，讲故事
       "zh-CN-XiaoshuangNeural",   # 女声，甜美轻松
   ]
   ```

3. **更新 `generate_tts()` 签名（第 38-42 行）**：
   - 新增参数：`rate: str = DEFAULT_RATE`、`pitch: str = DEFAULT_PITCH`、`break_ms: int = DEFAULT_BREAK_MS`
   - 将 `voice` 参数从关键字参数改为必选在 text/output_path 之后的可选参数（保持兼容）

4. **更新 `generate_tts()` 函数体（第 53-67 行）**：
   - 当任一参数非默认（rate!="+0%" 或 pitch!="+0Hz" 或 break_ms!=DEFAULT_BREAK_MS）时，走 SSML 路径：
     ```python
     tts_text = _build_ssml(text, rate=rate, pitch=pitch, break_ms=break_ms)
     communicate = Communicate(tts_text, voice)
     ```
   - 否则保持原路径 `Communicate(text, voice).save(output_path)` 确保向后兼容
   - 始终使用 `asyncio.wait_for(communicate.save(output_path), timeout=_TTS_TIMEOUT)` 不变

5. **更新 `generate_tts_safe()` 签名（第 70-93 行）**：
   - 新增转发参数：`voice: str = "zh-CN-XiaoxiaoNeural"`、`rate: str = DEFAULT_RATE`、`pitch: str = DEFAULT_PITCH`、`break_ms: int = DEFAULT_BREAK_MS`
   - 内部 `_attempt()` 调用 `generate_tts(text, output_path, voice=voice, rate=rate, pitch=pitch, break_ms=break_ms)` 转发所有参数

6. **更新 `__all__`（第 96 行）**：追加 `DEFAULT_BREAK_MS`、`DEFAULT_RATE`、`DEFAULT_PITCH`

**`src/xianyu/video/__init__.py`：**

7. **追加导入（第 47 行附近）**：`DEFAULT_BREAK_MS`、`DEFAULT_RATE`、`DEFAULT_PITCH`
8. **追加 `__all__` 条目（第 84-86 行区域）**

### 验收清单

- [ ] `_build_ssml()` 在 break_ms>0 时在句末插入 `<break/>`，break_ms=0 时不插入
- [ ] `_build_ssml()` 输出包含 `<speak>` + `<prosody rate/pitch>` 包装
- [ ] `generate_tts()` 默认参数行为与之前完全一致（不走 SSML 路径）
- [ ] `generate_tts()` 非默认参数时代码走 SSML 路径
- [ ] `generate_tts_safe()` 转发所有新增参数到 `generate_tts()`
- [ ] `get_available_voices()` 返回列表 >=5 条，包含新增 voice
- [ ] `DEFAULT_BREAK_MS` / `DEFAULT_RATE` / `DEFAULT_PITCH` 正确导出到 `video.__init__`
- [ ] 回归测试全部通过

### 验收

- [SSML break 注入正确]（参考：`uv run python3 -c "from xianyu.video.tts import _build_ssml; r=_build_ssml('你好。再见。'); assert '<break' in r; assert '<speak>' in r; print('OK')"`）
- [向后兼容]（参考：`cd ~/program/xianyu && uv run python3 -m pytest tests/video/test_tts.py -q --tb=short`）
- [常量可导入]（参考：`cd ~/program/xianyu && uv run python3 -c "from xianyu.video import DEFAULT_BREAK_MS, DEFAULT_RATE, DEFAULT_PITCH; print('OK')"`）

---

## 改动 2（Phase 2）：编排器参数透传 + ctx 配置通道 + 测试

### 做什么

将 Phase 1 新增的 TTS 参数（voice/rate/pitch/break_ms）通过编排器执行链路 `execute() → process() → _generate_tts()` 向下透传，并允许通过上层 `ctx` 字典在调用时配置。

**为什么需要这个改动：** 仅 Phase 1 只在 `video/tts.py` 新增了参数能力，但实际生产调用链 `execute(ctx) → process() → _generate_tts()` 没有传递参数的通道——`_generate_tts()` 始终使用默认值，等于没启用。

**预期效果：** 上层调用方可传入 `ctx["tts_voice"]="zh-CN-YunxiNeural"`、`ctx["tts_rate"]="+15%"` 等方式自定义 TTS 参数；不传时使用默认值，零改动。

### 怎么做

**`src/xianyu/content/video.py`：**

1. **import 区域（line 36 附近）**：清理当前 import。`_generate_tts` 中第 327 行的 `from xianyu.video.tts import generate_tts_safe` 移到文件顶部：
   ```python
   from ..video.tts import (
       DEFAULT_BREAK_MS, DEFAULT_PITCH, DEFAULT_RATE,
       generate_tts_safe,
   )
   ```

2. **`_generate_tts()` 签名（第 325 行）**改为：
   ```python
   async def _generate_tts(
       self,
       scenes: list[Scene],
       voice: str = "zh-CN-XiaoxiaoNeural",
       rate: str = DEFAULT_RATE,
       pitch: str = DEFAULT_PITCH,
       break_ms: int = DEFAULT_BREAK_MS,
   ) -> Path | None:
   ```
   第 334 行的 `generate_tts_safe` 调用改为：
   ```python
   result = await generate_tts_safe(
       full_text, str(output_path),
       voice=voice, rate=rate, pitch=pitch, break_ms=break_ms,
   )
   ```
   第 327 行的局部 import 删除（已移到文件顶部）。

3. **`process()` 签名（第 165 行）**：在 `ducking_db` 后新增 TTS 可选参数：
   ```python
   async def process(
       self,
       image_paths: list[str],
       script: str,
       output_path: Path,
       aspect: str = "9:16",
       ducking_db: float = DUCKING_DB,
       tts_voice: str = "zh-CN-XiaoxiaoNeural",
       tts_rate: str = DEFAULT_RATE,
       tts_pitch: str = DEFAULT_PITCH,
       tts_break_ms: int = DEFAULT_BREAK_MS,
   ) -> Path:
   ```

4. **`process()` 内 `_generate_tts()` 调用（第 198 行）**改为：
   ```python
   tts_path = await self._generate_tts(
       scenes, voice=tts_voice, rate=tts_rate,
       pitch=tts_pitch, break_ms=tts_break_ms,
   )
   ```

5. **`execute()` 内 `self.process()` 调用（第 109-115 行）**追加 TTS 参数：
   ```python
   result_path = await self.process(
       image_paths, script, output_path, aspect,
       ducking_db=ctx.get("ducking_db", DUCKING_DB),
       tts_voice=ctx.get("tts_voice", "zh-CN-XiaoxiaoNeural"),
       tts_rate=ctx.get("tts_rate", DEFAULT_RATE),
       tts_pitch=ctx.get("tts_pitch", DEFAULT_PITCH),
       tts_break_ms=ctx.get("tts_break_ms", DEFAULT_BREAK_MS),
   )
   ```

**`tests/video/test_tts.py`**：

6. **追加 Phase 2 测试（在现有测试之后）**：
   - `test_generate_tts_safe_forwards_params()`：mock `generate_tts`，验证 `generate_tts_safe` 转发全部 4 个新参数（voice/rate/pitch/break_ms）
   - `test_generate_tts_ssml_path()`：mock `Communicate`，验证非默认 rate 时调用 `_build_ssml` 构建的文本被传递给 `Communicate`
   - `test_generate_tts_default_plain_path()`：mock `Communicate`，验证默认参数时文本原样传递（非 SSML）

### 验收清单

- [ ] `_generate_tts()` 接受 voice/rate/pitch/break_ms 参数
- [ ] `process()` 接受 tts_voice/tts_rate/tts_pitch/tts_break_ms 参数并透传
- [ ] `execute()` 从 `ctx` 读取 TTS 参数（`ctx.get("tts_voice", ...)` 形式）
- [ ] 所有参数有合理默认值，不传时零行为变化
- [ ] import 组织清晰，重复 import 被消除
- [ ] 新增测试全部通过
- [ ] 回归测试全部通过

### 验收

- [参数透传测试]（参考：`cd ~/program/xianyu && uv run python3 -m pytest tests/video/test_tts.py -q --tb=short -k "params or ssml"`）
- [ctx 通道正常]（参考：审查代码，`execute()` 中 `ctx.get("tts_voice", ...)` 形式）
- [回归测试通过]（参考：`cd ~/program/xianyu && uv run python3 -m pytest tests/video/ -q --tb=short`）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | `video/tts.py` SSML + rate/pitch/break 注入 + voice 扩充 + `__init__.py` 导出 + 测试 | `feat(tts): add SSML break/pitch/rate injection + voice list expansion (phase 1/2)` |
| 2 | `content/video.py` 编排器三层参数透传 + ctx 配置通道 + 测试 | `feat(tts): wire voice/rate/pitch/break params through orchestrator (phase 2/2)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] 全部测试通过
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（2）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

1. 交付后可手动验证：在 API/CLI 调用层传入 `ctx={"tts_rate": "+15%", "tts_voice": "zh-CN-YunxiNeural"}`，确认 TTS 输出语速和音色变化
2. 后续可将 `tts_voice/rate/pitch/break_ms` 下放到内容模板（`TEMPLATES`）配置中，按内容类型（新闻/故事/教程）自动选择不同 voice 和 rate
3. 如需 word-level 字幕对齐（目前用 scene-level 时间线估算），可参考 `video-pipeline/stages/tts/generator.py` 的 `SubMaker` + `WordBoundary` 方案，但属于独立功能，非本任务范围
