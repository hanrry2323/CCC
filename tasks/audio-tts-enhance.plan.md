# Plan: audio-tts-enhance — TTS 语音增强 (edge-tts voice 调优 + break/pitch/rate 注入)

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

TTS 集中在 `video/tts.py` 和 `content/video.py`，edge-tts `Communicate` 调用仅传 `(text, voice)`，未利用其 `rate`/`pitch`/SSML 能力。

- **`src/xianyu/video/tts.py`**（96 行）— 核心 TTS 引擎，含 3 个公开函数：`generate_tts()` / `generate_tts_safe()` / `get_available_voices()`。`generate_tts()`（line 38-67）内部调用 `Communicate(text, voice).save()`，**无 rate/pitch 参数**。`generate_tts_safe()`（line 70-93）不接收 voice/rate/pitch 参数。
- **`src/xianyu/content/video.py`**（line 318-330）— `_generate_tts()` 调用 `generate_tts_safe()` 时**不传 voice**，始终使用默认语音 `zh-CN-XiaoxiaoNeural`。`process()`（line 109+ / 197-202）不提供 voice/rate/pitch 透传。
- **`src/xianyu/core/config.py`**（line 63）— 已定义 `mpt_default_voice` 但仅 MPT 后端使用，本地视频管线未引用。
- **voice 列表**（`tts.py:18-22`）— 仅 3 个中文语音（Xiaoxiao/Yunxi/Xiaohan），无 rate/pitch/volume 常量。
- **break 处理** — edge-tts 的 `Communicate` 原生支持 SSML（文本以 `<speak>` 开头自动检测），但当前无任何 SSML 生成逻辑。

---

## 范围

- **目标**：让 edge-tts `Communicate` 支持 voice 调优（可配）+ rate/pitch + SSML break 注入
- **只改文件**：
  - `src/xianyu/video/tts.py`
  - `src/xianyu/content/video.py`
  - `tests/video/test_tts.py`
- **不改文件**：`video/__init__.py`（导出不变）、`content/tts.py`（mock worker）、`core/config.py`（已有 `mpt_default_voice` 配置，不新增）、任何 `bridge/` 或 `orchestrator/` 文件
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1：`video/tts.py` — 函数签名扩展 + rate/pitch 注入 + break 注入 + voice 列表扩展

### 做什么

**A. voice 调优**
- 扩展 `_CHINESE_VOICES`：在已验证的基础上增加更多中文语音（如 `zh-CN-YunjianNeural`、`zh-CN-XiaochenNeural` 等），保留注释标识已验证集
- `generate_tts_safe()` 增加 `voice` 参数（默认 `"zh-CN-XiaoxiaoNeural"`），透传到 `generate_tts()`

**B. rate/pitch 注入**
- `generate_tts()` 增加 `rate: str = "+0%"` 和 `pitch: str = "+0Hz"` 参数
- `Communicate(text, voice).save(path)` → `Communicate(text, voice, rate=rate, pitch=pitch).save(path)`
- `generate_tts_safe()` 增加 `rate` / `pitch` 参数，透传到 `generate_tts()`

**C. break 注入**
- 新增私有函数 `_inject_ssml_breaks(text: str, break_ms: int = 500) -> str`：将连续两个换行 `\n\n` 替换为 `<break time="500ms"/>`（段落间自然停顿），包裹 `<speak>` 标签
- `generate_tts()` 在调用 `Communicate` 前调用 `_inject_ssml_breaks()`（可通过 `use_ssml: bool = True` 控制）
- edge-tts 在检测到 `<speak>` 开头时自动使用 SSML 模式，不需要额外标记

### 怎么做

**`src/xianyu/video/tts.py`**：

1. Line 17-22，扩展 voice 列表：
   ```python
   _CHINESE_VOICES: Final[list[str]] = [
       "zh-CN-XiaoxiaoNeural",    # 女性，普通话 — 默认
       "zh-CN-YunxiNeural",       # 男性，普通话
       "zh-CN-XiaohanNeural",     # 女性，温柔/亲切
       "zh-CN-XiaochenNeural",    # 女性，轻松/活力
       "zh-CN-YunjianNeural",     # 男性，沉稳
   ]
   ```

2. Line 24，添加 SSML break 常量和注入函数（在 `_RETRY_DELAY` 常量之后）：
   ```python
   _SSML_BREAK_MS: Final[int] = 500  # paragraph break duration (ms)
   
   def _inject_ssml_breaks(text: str, break_ms: int = _SSML_BREAK_MS) -> str:
       """Wrap text in SSML with <break/> between paragraph breaks (double newlines).
       
       edge-tts auto-detects SSML when text starts with '<speak>'.
       """
       if text.startswith("<speak>"):
           return text
       # split on double newlines (paragraph boundaries)
       lines = text.split("\n\n")
       if len(lines) <= 1:
           return text
       breaks = "\n".join(f"<break time=\"{break_ms}ms\"/>\n{para}" if i > 0 else para
                         for i, para in enumerate(lines))
       return f"<speak>{breaks}</speak>"
   ```

3. Line 38-67，`generate_tts()` 签名和调用体：
   - 签名增加 `rate: str = "+0%"`, `pitch: str = "+0Hz"`, `use_ssml: bool = True`
   - 在 `try` 块内：`text = _inject_ssml_breaks(text)` if `use_ssml`
   - `Communicate(text, voice, rate=rate, pitch=pitch).save(output_path)`
   - 日志增加 rate/pitch 信息
   - `__all__` 新增 `"generate_tts_safe"`(already there), no new public symbols needed

4. Line 70-93，`generate_tts_safe()`：
   - 签名增加 `voice: str = "zh-CN-XiaoxiaoNeural"`, `rate: str = "+0%"`, `pitch: str = "+0Hz"`, `use_ssml: bool = True`
   - `_attempt()` 内透传 `generate_tts(text, output_path, voice=voice, rate=rate, pitch=pitch, use_ssml=use_ssml)`

### 验收清单

- [ ] `generate_tts()` 签名新增 `rate`/`pitch`/`use_ssml` 参数
- [ ] `generate_tts_safe()` 签名新增 `voice`/`rate`/`pitch`/`use_ssml` 参数
- [ ] `Communicate()` 调用传入 `rate`/`pitch` 参数
- [ ] `_inject_ssml_breaks()` 将 `\n\n` 段落分隔转换为 SSML `<break/>` 标签
- [ ] 已有 3 个公开函数签名保持向后兼容（新参数有默认值）
- [ ] `_CHINESE_VOICES` 扩展到 5 个以上中文语音

### 验收

- [rate/pitch 参数生效]（参考：`cd ~/program/xianyu && uv run python3 -c "from xianyu.video.tts import generate_tts; import inspect; sig = inspect.signature(generate_tts); print({k: v.default for k, v in sig.parameters.items() if k in ('rate','pitch','use_ssml')})"`）
- [SSML break 注入逻辑正确]（参考：`cd ~/program/xianyu && uv run python3 -c "from xianyu.video.tts import _inject_ssml_breaks; print(_inject_ssml_breaks('a\n\nb'))"` — 应输出包含 `<speak>`+`<break/>` 的字符串）

---

## 改动 2：`content/video.py` — 透传 voice/rate/pitch 到 TTS

### 做什么

让 `_generate_tts()` 从配置和场景上下文中获取 voice/rate/pitch，传递到 `generate_tts_safe()`。

- `_generate_tts()` 签名增加 `voice`/`rate`/`pitch` 可选参数
- `process()` 中 `_generate_tts()` 调用时传入配置值
- voice 默认源：`get_settings().mpt_default_voice`
- rate/pitch 默认值：`"+0%"` / `"+0Hz"`（可配，但不新增 config 字段）

### 怎么做

**`src/xianyu/content/video.py`**：

1. Line 318-330，`_generate_tts()`：
   ```python
   async def _generate_tts(
       self,
       scenes: list[Scene],
       voice: str = "zh-CN-XiaoxiaoNeural",
       rate: str = "+0%",
       pitch: str = "+0Hz",
   ) -> Path | None:
       """为所有场景合生成 TTS 音频。"""
       from xianyu.video.tts import generate_tts_safe
       
       full_text = "。".join(s.caption for s in scenes if s.caption)
       if not full_text.strip():
           return None
       
       output_path = self.temp_dir / f"tts_{uuid.uuid4().hex[:8]}.mp3"
       result = await generate_tts_safe(
           full_text, str(output_path),
           voice=voice, rate=rate, pitch=pitch,
       )
       if result:
           return Path(result)
       return None
   ```

2. `process()` 中（line 197-202），`_generate_tts()` 调用改为：
   ```python
   tts_path = await self._generate_tts(
       scenes,
       voice=get_settings().mpt_default_voice,
   )
   ```
   （rate/pitch 使用默认 `"+0%"` / `"+0Hz"`，暂不引入 context 层透传）

### 验收清单

- [ ] `_generate_tts()` 签名增加 `voice`/`rate`/`pitch` 参数
- [ ] `process()` 从 config 读 `mpt_default_voice` 传给 `_generate_tts()`
- [ ] `_generate_tts()` 透传 voice 到 `generate_tts_safe()`
- [ ] 现有调用路径（`_generate_tts(scenes)`）仍工作（新参数有默认值）

### 验收

- [voice 透传]（参考：mock `generate_tts_safe` 调用，验证 `voice` 参数被传入）
- [默认值向后兼容]（参考：`cd ~/program/xianyu && uv run python3 -m pytest tests/video/test_tts.py -q --tb=short` 全部通过）

---

## 改动 3：测试更新

### 做什么

为 `video/tts.py` 新增的 rate/pitch/SSML 功能添加测试覆盖：

- `test_generate_tts_with_rate_pitch` — 验证速率和音高参数被传递给 Communicate
- `test_generate_tts_safe_with_voice_rate_pitch` — 验证 safe 版本透传所有参数
- `test_inject_ssml_breaks` — 验证 `_inject_ssml_breaks()` 的逻辑
- `test_inject_ssml_breaks_no_changes` — 无段落分隔时保持原文本
- `test_generate_tts_with_ssml` — 验证 SSML 文本被传递给 Communicate
- 已有测试更新：`test_generate_tts_success` 验证 `generate_tts` 调用使用正确的 `rate`/`pitch` 默认值

### 怎么做

**`tests/video/test_tts.py`**（追加在末尾）：

- `test_generate_tts_with_rate_pitch()` — `patch("edge_tts.Communicate")`，验证 `Communicate` 被用 `rate="-20%"` `pitch="+10Hz"` 调用，`save` 被 await
- `test_generate_tts_safe_with_voice_rate_pitch()` — `patch("xianyu.video.tts.generate_tts")`，验证 `generate_tts` 被用 `voice="zh-CN-YunxiNeural"` `rate="-10%"` 调用
- `test_inject_ssml_breaks()` — 输入 `"a\n\nb"` → 期望包含 `<speak>`、`<break time="500ms"/>`、`a`、`b`
- `test_inject_ssml_breaks_no_changes()` — 输入 `"a b"`（无段落分隔）→ 返回原文本
- `test_inject_ssml_breaks_already_ssml()` — 输入 `<speak>xxx</speak>` → 返回原文本
- 更新 `test_generate_tts_success()` — 断言 `Communicate` 被 `rate="+0%"` `pitch="+0Hz"` 调用

### 验收清单

- [ ] 新增 5 个测试全部通过
- [ ] 已有 12 个回归测试全部通过（0 退化）
- [ ] ruff lint + mypy --strict 无新增错误

### 验收

- [新增测试通过]（参考：`cd ~/program/xianyu && uv run python3 -m pytest tests/video/test_tts.py -q --tb=short -k "rate or pitch or ssml or break"`）
- [全部 TTS 测试通过]（参考：`cd ~/program/xianyu && uv run python3 -m pytest tests/video/test_tts.py -q --tb=short`）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | voice 调优 + rate/pitch + SSML break 注入 + 管线集成 + 测试 | `feat(tts): edge-tts voice tuning, rate/pitch params, and SSML break injection (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`mypy --strict`）
- [ ] 全部 TTS 测试通过
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（1）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

1. 验收后可在生产环境中验证效果：依次调整 `content/video.py` 中的 rate/pitch 值，比较不同参数下的 TTS 输出质量
2. 如需按 topic/subject 动态选择 voice，后续可在 `core/config.py` 增加 voice-per-topic 映射，或由 LLM 生成 TTS 参数
