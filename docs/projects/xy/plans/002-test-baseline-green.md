# 方案 · 测试基线绿（M2-2.1）

> 项目：xy · 编号：xy-plan-002 · 状态：已确定 · 作者：Claude（中枢） · 工具：Claude Code
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：无
> 关联方案：无
> 里程碑：M2 · 生产就绪
> 子项目：2.1 测试基线绿
> 环境准备：mac2017 xianyu 业务仓可写（`/Users/fan/program/apps/xianyu`）；`playwright install chromium` 可执行

## 目标

把 xianyu 业务仓 7 个红测全部归零，`pytest` 从「662 passed / 7 failed / 8 skipped」恢复到全绿基线，作为生产就绪的第一道门。

## 背景

xy 债务清理后代码本体健康（677 用例），但 `pytest` 不能全绿——7 个失败分三类：**环境类**（2 个，playwright chromium 未安装）、**过时断言**（1 个，launchd plist 断言在清理后已无 plist）、**测试与真实行为脱节**（4 个，rewriter 测试假设「无 live Ollama」但代码是 Ollama 真改写 + mock 兜底；BGM 选择/重试次数断言偏差）。这些红测不修，生产就绪无基线，后续任何开发无法判断是否引入回归。

## 方案内容

按红测根因分四类处理，每类一张功能卡：

1. **环境补装**（2 个红测：`tests/html_scene/test_renderer.py::test_with_basic_html` / `test_output_directory_structure`）：`playwright install chromium` 补装浏览器，红测转绿。
2. **过时断言更新**（1 个：`tests/openclaw/test_plugin_integration.py::test_launchd_plists_use_pipeline_cron`）：清理已删 launchd plist，测试还断言 `len(plists) == 10`——改为断言「无 xianyu launchd plist（或按重建后的运行方式断言）」。
3. **rewriter mock 隔离**（2 个：`test_execute_generates_4_platform_versions` / `test_execute_truncates_correctly`）：测试假设 Ollama 离线走 mock，但 `rewriter.py` 实际在线调 Ollama（`.env` 配了 `OLLAMA_MODEL=flash`）——测试需显式 mock Ollama 调用（monkeypatch），隔离非确定性。
4. **逻辑断言修正**（2 个：`test_daily_image_source::TestOllamaFallback::test_primary_model_failure_triggers_fallback` 期望重试 3 次实际 1 次；`test_bgm_tags::TestMatchBgm::test_exclude_avoids_duplicate` 期望 `bright.mp3` 实际 `calm.mp3`）——逐一核实代码行为，修断言或修代码（行为正确则改断言，行为有误则修代码）。

## 验收标准

- [ ] `pytest`（业务仓）全绿：0 failed（当前 7 failed → 0）
- [ ] 环境类红测补装 chromium 后通过
- [ ] rewriter 测试不再依赖真实 Ollama 在线调用（显式 mock）
- [ ] 无「为了绿而绿」的断言弱化（每个修正都有根因说明）

## 功能卡

### 环境补装 chromium

目标：2 个 html_scene 红测因 playwright chromium 未安装失败，补装浏览器使渲染测试可跑。

实现：在 mac2017 xianyu 业务仓 `.venv` 执行 `playwright install chromium`；确认 `tests/html_scene/test_renderer.py` 两个用例转绿。

验收：`pytest tests/html_scene/test_renderer.py` 通过。

颗粒度：环境补装，单机单操作，无代码改动。

依赖：无

架构位置：测试环境（html_scene HTML→帧渲染测试依赖 playwright 浏览器）

### 过时 launchd 断言更新

目标：`test_launchd_plists_use_pipeline_cron` 断言 10 个 launchd plist，但债务清理已删——更新断言匹配现状。

实现：核实 `scripts/` 里 launchd 相关扫描逻辑，按「清理后无 xianyu launchd plist（或重建后按新运行方式）」修正断言。

验收：`pytest tests/openclaw/test_plugin_integration.py` 通过，断言反映真实运行方式。

颗粒度：单测试断言修正，不改生产逻辑。

依赖：无

架构位置：测试层（openclaw 集成测试）

### rewriter 测试 mock 隔离

目标：rewriter 两个测试因真实 Ollama 在线调用产生非确定性输出而失败，改为显式 mock。

实现：在测试中 monkeypatch `src/xianyu/core/llm.py` 的 chat 调用（或 `rewriter.py` 的 LLM 依赖），使 `test_execute_generates_4_platform_versions` 与 `test_execute_truncates_correctly` 走确定的 mock 路径。

验收：两个 rewriter 测试转绿，且不再触发真实 Ollama 调用。

颗粒度：测试隔离改造，单模块。

依赖：无

架构位置：测试层（content/rewriter 测试）

### 逻辑断言修正（BGM 选择 + 重试次数）

目标：两个断言与真实行为脱节，逐一核实后修断言或修代码。

实现：`test_bgm_tags::TestMatchBgm::test_exclude_avoids_duplicate` 核实 BGM 选择逻辑（为何返回 calm 而非 bright，行为是否正确）；`test_daily_image_source::TestOllamaFallback` 核实重试次数（期望 3 次实际 1 次，重试逻辑是否正确）。行为正确→改断言；行为有误→修代码。

验收：两个测试转绿，每个修正附根因说明。

颗粒度：每项独立核实，各 1 处小改动。

依赖：无

架构位置：测试层 + 可能 src/xianyu/video/ 或 src/xianyu/ops/ 逻辑

## 转卡计划

环境补装 chromium / 过时 launchd 断言更新 / rewriter 测试 mock 隔离 / 逻辑断言修正（BGM + 重试）

## 备注

- 验收以「0 failed」为硬门，但反对「为绿而绿」——每个修正都要带根因。
- 修完后跑全量 `pytest` 确认 677 用例全绿（含此前 8 skipped，不强制补 skipped，除非与生产就绪相关）。
