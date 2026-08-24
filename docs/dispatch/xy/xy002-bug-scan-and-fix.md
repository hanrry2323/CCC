# 任务卡 xy002 · xy代码bug全量扫描与修复（OpenCode 执行）

> 关联：xy-plan-001 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 目标

把 xianyu 仓代码 bug 全量扫一遍，出修复方案，并按方案修复到可验证通过。

## 红线（先看）

1. 只动 2017 `/Users/fan/program/apps/xianyu` 仓；不碰平台（CCC server/engine/board）与其他项目。
2. 不直推 main；走卡内分支 `codex/xy002-bug-scan-and-fix`。
3. 扫描须真实执行（静态扫描 + 按仓内现有测试跑一遍），不得凭空列 bug 凑数。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- xianyu 仓全量代码 bug 扫描（含入口脚本 / 主逻辑 / 配置）。
- 产出「bug 清单 + 修复方案」：每条 bug 含 现象 / 定位 / 修法 / 优先级。
- 按方案修复，修复后跑仓内现有测试/自检确认通过。

## 步骤

1. **扫描**：读 xianyu 仓结构 → 静态扫描（明显错误、异常未处理、路径/文件名硬编码、产出流程漏洞）→ 跑仓内现有测试或最小自检，记录结果。
2. **出方案**：把 bug 清单 + 修复方案写进回写区「扫描报告」（每条：现象/定位/修法/优先级）。
3. **修复**：按方案逐条修（优先修 P0/P1）；每修一条记一句改了什么。
4. **回归**：修复后重跑扫描项与仓内测试，确认修复不引入新问题。
5. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区

` / 置「已关闭」。等 2017 机审 → 老板「验收看板」终验。

## 验收标准

1. 回写区有「扫描报告」：bug 清单每条含 现象/定位/修法/优先级，且来自真实扫描（附证据：扫描命令输出、测试运行结果）。
2. 至少 P0/P1 bug 已修复并回归通过（附修复后测试/自检输出）。
3. 修复不越界：只动 xianyu 仓，改动可逐条对上扫描报告的 bug。
4. 若扫描结果为零 bug，必须给出扫描范围与依据（禁止空手交差）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人工终验听「验收看板」后写 `## 验收区`+已关闭。

## 验收区

**合入批准** · 日期：2026-08-12
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 1. 扫描报告 (Bug 扫描与修复方案)

*   **Bug 1 (P0): `xianyu/video/encoding.py` 语法错误导致模块无法导入**
    *   **现象**: `import xianyu.video.encoding` 报 `SyntaxError: 'await' outside async function` 语法错误，导致模块 100% 损坏，无法被导入或进行 Coverage 扫描。
    *   **定位**: `run_2pass_encoding` 被声明为普通 `def` 函数，但内部却包含对 `_run_pass` 的 `await`。
    *   **修法**: 将 `run_2pass_encoding` 改为 `async def run_2pass_encoding`。
    *   **状态**: **已修复**。

*   **Bug 2 (P1): `xianyu/video/encoding.py` 中 `profile.encoder.value.lower()` 引发 AttributeError**
    *   **现象**: 在构建 FFmpeg 编码参数时，直接调用 `profile.encoder.value.lower()` 报错 `AttributeError: 'int' object has no attribute 'lower'`。
    *   **定位**: `EncoderType` 继承自 `Enum` 且使用 `auto()` 声明，因此其 `value` 是整型数字，没有 `lower()` 方法。
    *   **修法**: 在 `EncoderType` 上增加一个 `ffmpeg_codec` 属性，建立到 FFmpeg 实际编码器名（`libx264` / `libx265` / `h264_videotoolbox` 等）的映射字典，并在构建参数时通过 `profile.encoder.ffmpeg_codec` 引用。
    *   **状态**: **已修复**。

*   **Bug 3 (P1): `xianyu/video/encoding.py` 中 `get_profile` 函数参数 `encoder_override` 类型不安全**
    *   **现象**: `encoder_override` 传入类型声明为 `str | None`，当传入非空字符串时，会直接将 `profile.encoder` 赋值为字符串，导致在参数构建阶段获取 `profile.encoder` 属性报错。
    *   **定位**: `get_profile` 的 `encoder_override` 处理流程与类型声明不一致。
    *   **修法**: 限制 `encoder_override` 参数的类型为 `EncoderType | None`，在 assignment 阶段声明并固化 `encoded` 的 `EncoderType` 类型。
    *   **状态**: **已修复**。

*   **Bug 4 (P3): 散落的其它 pre-existing 报错与遗留项**
    *   **现象/定位**: Ruff 静态分析发现 `xianyu/orchestrator/pipeline.py` 中存在大量未使用导入 (F401)，`local_writer.py` 存在过时类型标注 (UP035)。
    *   **修法**: 运行 `ruff check --fix` 清理未使用导入和过时标注。
    *   **状态**: **已修复**（且所有单元测试均正常通过，无 re-export 破坏）。

---

### 2. 测试验证证据

*   **全量单元与集成测试**: 跑完 `xianyu` 仓内全量测试（除去由于网络环境等被 marked skipped 的 e2e 外部测试外），本地单元、集成、存储、路由与 Bridge 测试 100% 成功。
    ```bash
    .venv/bin/pytest -o addopts="" -q --tb=short tests/unit tests/integration tests/utils tests/core tests/ops tests/storage tests/html_scene tests/bridge
    # 输出: 246 passed, 3 skipped, 57 warnings in 6.21s
    ```
*   **编码模块专属测试**: 针对 `encoding.py` 专门编写并合入了专属测试 `tests/video/test_encoding.py`，完整覆盖 CRF 预设生成、2pass VBR 状态流转以及异步 FFmpeg mock 进程调度的成功分支（Pass 1 + Pass 2），顺利通过。
    ```bash
    .venv/bin/pytest -o addopts="" -q --tb=short tests/video/test_encoding.py
    # 输出: 7 passed in 0.48s
    ```
*   **静态与类型检查验证**: mypy 与 ruff 对修改过的文件完全检查通过（mypy success, ruff zero checks failed）。

---

### 3. Push 证据

*   **xianyu 业务仓分支**: `codex/xy002-bug-scan-and-fix`
*   **xianyu Commit Hash**: `dbd1ef2bc34bd2c56428e4572ddc6cb2fb27cdf9`

## 机审区

**机审席**：Claude Code · 日期：2026-08-07

**独立取证结论**：通过

- **取证对象**：xianyu 仓 `codex/xy002-bug-scan-and-fix` 分支，HEAD `dbd1ef2`（已核对与回写 commit hash 一致；`git status` ahead 1，未直推 main）。
- **Bug 1 (P0) 复核**：pre-fix 编译即报 `SyntaxError: 'await' outside async function`（`run_2pass_encoding` 为普通 def 且顶层 `await _run_pass`）。修复后 `async def run_2pass_encoding`，`src/xianyu/video/encoding.py` 编译/导入 OK。✅ 与报告一致。
- **Bug 2 (P1) 复核**：`EncoderType` 用 `auto()` → `.value` 是 int；pre-fix `profile.encoder.value.lower()` 必抛 AttributeError。修复新增 `ffmpeg_codec` 属性映射到真实 FFmpeg 编码器名，参数构建改用 `.ffmpeg_codec`。✅ 与报告一致。
- **Bug 3 (P1) 复核**：`get_profile` 参数由 `encoder_override: str|None` 收紧为 `EncoderType|None`，消除字符串赋值的类型不安全。✅ 与报告一致。
- **Bug 4 (P3) 复核**：pipeline.py 移除 6 个未使用 import（F401），local_writer.py 清理 UP035。✅ 与报告一致。
- **回归证据（独立重跑）**：
  - `tests/video/test_encoding.py` → **7 passed** ✅
  - 全量（unit/integration/utils/core/ops/storage/html_scene/bridge）→ **246 passed, 3 skipped, 57 warnings** ✅（与回写一致）
- **范围核对**：代码改动仅在 xianyu 仓（`src/xianyu/` + `tests/video/test_encoding.py`），未触碰 CCC 平台，未越界写验收区/已关闭。✅
- **非阻断备注**：`run_2pass_encoding` 在生产 `src/` 无调用方（仅新增测试调用，属此前不可用的死代码）；修复本身正确且消除了文件级 import 阻断，不影响验收。

== 机审：通过 ==

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
