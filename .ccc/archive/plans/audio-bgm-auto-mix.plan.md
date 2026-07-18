# Plan: audio-bgm-auto-mix — 自动 BGM 混音：后混音输出归一 + bgm_volume 配置化

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

音频混音管线已有完整的 `mix_audio()` 和 `build_bgm_filter_chain()`, 包含 amix normalize=1 的自动增益匹配和 sidechaincompress ducking, 但存在 4 个重要断点：

- **`src/xianyu/video/bgm.py`**: `mix_audio()`（line 149）和 `build_bgm_filter_chain()`（line 64）的 BGM 音量硬编码为 `BGM_VOLUME=0.3`。`mix_audio()` 的 TTS+BGM 分支在 amix 合并后没有后处理动力归一——输出电平随输入材差距变化。
- **`src/xianyu/content/video.py`**: 两处 `mix_audio()` 调用（line 219 和 line 601）使用 `__import__("xianyu.video").video.DUCKING_DB` 作为 ducking_db 兜底——Python 的 `__import__("xianyu.video")` 返回顶层包，其 `video` 属性是子模块名而非值，运行时引发 `AttributeError`（被外层 `try/except` 静默，但兜底失效）。`ducking` 参数从不穿透，恒为 True。`bgm_volume` 参数不存在。
- **`src/xianyu/video/__init__.py`**: 已导出所有 BGM 常量。
- **`tests/video/test_bgm.py`**: 覆盖 ducking on/off、ratio 映射、ducking_db 默认值，无 `bgm_volume` 测试、无后混音归一测试。

---

## 范围

- **目标**：为自动 BGM 混音添加后混音输出归一（final dynaudnorm）+ `bgm_volume` 配置化参数 + 修复 video.py 中兜底 import bug + 全线穿透 pipeline context
- **只改文件**：
  - `src/xianyu/video/bgm.py`
  - `src/xianyu/content/video.py`
  - `tests/video/test_bgm.py`
- **不改文件**：`src/xianyu/video/__init__.py`（`DUCKING_DB` 已导出），任何 `video-pipeline/` 文件
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1：后混音输出归一 + bgm_volume 配置化 + 修复 video.py import

### 做什么

当前 `mix_audio()` 的 `amix` 部分虽然有 `normalize=1`（自动 gain 匹配), 但混合后的输出端没有动力归一化。当 TTS 和 BGM 各自归一后 amix 的输出电平仍可能不一致（材料差异 + 不同 ducking 深度导致）。

需要：
1. `mix_audio()` 的 TTS+BGM 分支在 `[aout]` 输出前加一级 `dynaudnorm`，确保混合后输出音量稳定一致。仅在 TTS+BGM 两条流都存在时启用此后级归一。
2. `mix_audio()` 新增 `bgm_volume: float = BGM_VOLUME` 关键字参数，替代 filter 中的硬编码 `volume={BGM_VOLUME}`，使 BGM 相对 TTS 的音量可通过参数调节。
3. `build_bgm_filter_chain()` 同步新增 `bgm_volume` 参数，保持两个混音接口对称。
4. `content/video.py` 修复 ducking_db 兜底 import bug（`from xianyu.video.bgm import DUCKING_DB`），补传 `ducking` 参数（`ctx.get("ducking", True)`），新增 `bgm_volume` 穿透（`ctx.get("bgm_volume", BGM_VOLUME)`）。
5. 测试覆盖 `bgm_volume` 自定义值、后混音 dynaudnorm 存在性、默认值向后兼容。

### 怎么做

**`src/xianyu/video/bgm.py`**：

1. **`mix_audio()`（line 149）签名变更**：
   ```python
   async def mix_audio(
       tts_path: str,
       bgm_path: str,
       output_path: str,
       duration: float,
       *,
       ducking: bool = True,
       ducking_db: float = DUCKING_DB,
       bgm_volume: float = BGM_VOLUME,  # ← 新增
   ) -> str:
   ```

2. **`mix_audio()` filter 构建（line 192-228）**：
   - 所有 `volume={BGM_VOLUME}` 改为 `volume={bgm_volume}`（两条 filter 构造路径：line 201 和 line 245）
   - TTS+BGM 分支 ducking 路径（line 217-219）：amix 后加一级 `dynaudnorm`：
     ```python
     # 改为两段
     filter_parts.append(
         "[tts_norm][bgm_ducked]amix=inputs=2:duration=first:normalize=1[mix_out]"
     )
     filter_parts.append("[mix_out]dynaudnorm=p=0.95[s=0.001][aout]")
     ```
   - TTS+BGM 分支 no-ducking 路径（line 223-224）：同样加一级 dynaudnorm：
     ```python
     filter_parts.append(
         "[tts_norm][bgm_proc]amix=inputs=2:duration=first:normalize=1[mix_out]"
     )
     filter_parts.append("[mix_out]dynaudnorm=p=0.95[s=0.001][aout]")
     ```
   - TTS-only、BGM-only 分支保持不变（它们已有独立归一逻辑）

3. **`build_bgm_filter_chain()`（line 64）签名变更**：
   ```python
   def build_bgm_filter_chain(
       tts_path: str,
       bgm_path: str,
       video_duration: float,
       ducking: bool = True,
       ducking_db: float = DUCKING_DB,
       bgm_volume: float = BGM_VOLUME,  # ← 新增
   ) -> list[str]:
   ```
   - 内部 `volume={BGM_VOLUME}`（line 98）改为 `volume={bgm_volume}`
   - amix 后（line 120 和 123）加 dynaudnorm 输出归一，参数一致

4. **`build_bgm_filter_chain()` amix 参数对齐**：
   - 当前 `build_bgm_filter_chain()` 使用 `dropout_transition=2`（与 `mix_audio()` 的 `normalize=1` 不同）。改为与 `mix_audio()` 一致的两段式：amix + dynaudnorm，保持 normalize=1。
   - 修改 line 120：`"[0:a][{ducked_label}]amix=inputs=2:duration=first:normalize=1[mix_out]"` + 追加 `"[mix_out]dynaudnorm=p=0.95[s=0.001]"`
   - 修改 line 123：同上模式

5. **`__all__`（line 367）**：不需要变更（BGM_VOLUME 已在 `__all__` 中）

**`src/xianyu/content/video.py`**：

1. **顶部 import 区（~line 30）新增**：
   ```python
   from xianyu.video.bgm import DUCKING_DB
   ```

2. **第一个调用点（line 219-225）改为**：
   ```python
   await mix_audio(
       tts_arg,
       bgm_arg,
       str(mixed_audio_path),
       total_duration,
       ducking=ctx.get("ducking", True),
       ducking_db=ctx.get("ducking_db", DUCKING_DB),
       bgm_volume=ctx.get("bgm_volume", __import__("xianyu.video").video.BGM_VOLUME),  # 注意这里用 BGM_VOLUME
   )
   ```
   > 说明：`ducking` 和 `bgm_volume` 从 ctx context dict 取，兜底用常量。`bgm_volume` 的兜底可用 `from xianyu.video.bgm import BGM_VOLUME`（与 DUCKING_DB 同一 import 行）。**删除**原来 `__import__("xianyu.video").video.DUCKING_DB` 写法。

3. **第二个调用点（line 601-607）同样修改**：
   ```python
   await mix_audio(
       tts_arg,
       bgm_arg,
       str(mixed_path),
       total_duration,
       ducking=ctx.get("ducking", True),
       ducking_db=ctx.get("ducking_db", DUCKING_DB),
       bgm_volume=ctx.get("bgm_volume", BGM_VOLUME),
   )
   ```

**`tests/video/test_bgm.py`**：

1. **`test_build_filter_chain_with_ducking()`（line 77）**：现在 filter 数为 4（原来 3 + 新的 dynaudnorm）。断言改为 `len(filters) == 4`，且最后一个 filter 包含 `dynaudnorm`。
2. **`test_build_filter_chain_no_ducking()`**：filter 数变为 3（原来 2 + dynaudnorm），检查最后包含 `dynaudnorm`。
3. **新增 `test_build_filter_chain_bgm_volume_custom()`**：传 `bgm_volume=0.5`，验证 filter 字符串包含 `volume=0.5`。
4. **新增 `test_build_filter_chain_post_mix_dynaudnorm()`**：验证 ducking 和 no-ducking 分支的 amix 后均有 `dynaudnorm` 段。
5. **`test_mix_audio_tts_and_bgm_with_ducking()`（现有）**：更新 mock 检查，filter 字符串应包含 `[mix_out]` + `[aout]` 分段，ratio assertion 不变。
6. **新增 `test_mix_audio_bgm_volume_custom()`**：mock ffmpeg，传 `bgm_volume=0.5`，assert filter 含 `volume=0.5`。
7. **新增 `test_mix_audio_tts_only()`/`test_mix_audio_bgm_only()`**：验证 TTS-only 和 BGM-only 分支不受 bgm_volume 影响（不出现 volume 参数在 TTS-only 中，BGM-only 中用 `volume=0.5` 时使用传入 bgm_volume）。
8. **`test_mix_audio_no_ducking()`（现有）**：更新 filter 格式断言，确认 `[mix_out]` 分段。

### 验收清单

- [ ] `mix_audio()` 接受 `bgm_volume` 关键字参数，默认 `BGM_VOLUME=0.3`
- [ ] `build_bgm_filter_chain()` 接受 `bgm_volume` 关键字参数，默认 0.3
- [ ] TTS+BGM 分支输出端永久加一级 `dynaudnorm`（filter 分段为 amix→mix_out→dynaudnorm→aout）
- [ ] `content/video.py` 两处调用不再使用 `__import__("xianyu.video").video.DUCKING_DB`，改为正确定义 import
- [ ] `content/video.py` 两处调用穿透 `ducking` 和 `bgm_volume`（从 ctx.get）
- [ ] TTS-only 和 BGM-only 分支不受 `bgm_volume` 影响
- [ ] `build_bgm_filter_chain()` 的 amix 参数对齐 `mix_audio()`（normalize=1 + dynaudnorm, 替代 dropout_transition=2）
- [ ] 回归测试全部通过
- [ ] ruff lint + mypy --strict 无新增错误
- [ ] 向后兼容：不传 `bgm_volume` 的调用自动使用 0.3

### 验收

- [bgm_volume 参数传递]（参考：`python3 -m pytest tests/video/test_bgm.py -q --tb=short -k "bgm_volume"`）
- [后混音 dynaudnorm]（参考：`python3 -m pytest tests/video/test_bgm.py -q --tb=short -k "dynaudnorm or post_mix"`）
- [ducking_db import 修复]（参考：`python3 -m pytest tests/ -q --tb=short -k "not e2e" --ignore=tests/e2e`）
- [回归测试]（参考：`cd ~/program/xianyu && python3 -m pytest tests/video/ -q --tb=short`）
- [lint + type]（参考：`cd ~/program/xianyu && uv run ruff check src/xianyu/video/bgm.py src/xianyu/content/video.py && uv run mypy --strict src/xianyu/video/bgm.py src/xianyu/content/video.py`）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | bgm_volume 参数 + 后混音 dynaudnorm + 修复 video.py import + 测试 | `feat(audio): add bgm_volume param, post-mix dynaudnorm, fix broken ducking_db import (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误
- [ ] 全部测试通过
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致（1）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

本任务完成后的建议顺序：`audio-voice-duck`（已并行完成）→ `audio-level-norm`（A3, LUFS 全文件归一化）→ 音频管线收尾。
