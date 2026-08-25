# 任务卡 xy056 · Playwright 帧渲染器（M5-1）— HTML 场景→帧→视频主链路合拢（OpenCode 执行）

> 关联：xy-plan-008 · 执行体：OpenCode · 验收：OpenCode · 状态：作废（老板定夺作废：OpenCode 时代卡、机审不通过、关联 xy-plan-008） · 派发：engine · 项目：xy · 日期：2026-08-20
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/xy/README.md`
- 方案池：`docs/projects/xy/plans/`（关联方案见卡头「关联」，本卡 = xy-plan-008 功能卡 5.1 Playwright 帧渲染器）
- **依赖链（2026-08-21 修订）**：本卡无代码级依赖（承接 M3 已落地的 html_scene + Hyperframes），可立即启动。与 xy055/xy057 并行开发，合入时各自验证。M6 API（xy052-xy054）不影响本卡开发。

## 目标

补齐 HTML→Video 主链路缺失段：HTML 场景→帧序列→视频合成稳定管线（Playwright headless 截帧，按口播时长定帧数，CSS 动画自动执行），Playwright 不可用自动降级现有管线，生产不中断。

## 实现

①`video-pipeline/stages/scene/` 新增 frame capture：Playwright headless 截帧（1920×1080 / 1080×1920 竖屏为主，30fps，场景按口播时长计算帧数，等待 CSS 动画执行）。

②帧序列 FFmpeg 合成（沿用已有编码参数，参照 xy-plan-006 质量量化标准：码率 0.12→3.7 Mbps 线）。

③Playwright 不可用/失败 → 自动降级现有渲染管线（PIL 线程池回退），生产不中断。

④补测试：fixtures 覆盖 Playwright 可用/不可用两路径，验证降级。

## 红线（先看）

1. 生产不中断：降级路径必须完整可用，禁止因 Playwright 缺失阻塞生产
2. 只动 `video-pipeline/stages/scene/` 及测试；禁止改动其他生产链路（topic/writer/rewriter/image/tts/video 各 stage 既有行为不变）
3. 环境前置（2017）：`pip install playwright` + chromium 需安装验证；安装失败不得改代码硬编码降级逻辑绕过

## 范围

- `video-pipeline/stages/scene/`（新增 frame_capture + html_composer 模块）
- 测试文件（`tests/` 新增）
- 禁止改动：`src/xianyu/` 下生产文件；其他 pipeline stage

## 步骤

1. 读方案 xy-plan-008 功能卡「Playwright 帧渲染器」+ 现有 `video-pipeline/stages/scene/` 结构（html_scene 骨架：agent/schema/renderer）+ Hyperframes 集成（xy047/xy048 产物）
2. 2017 环境验证：`pip install playwright` + chromium 可启动（失败先解决环境，勿改代码绕过）
3. 实现 frame capture（headless 截帧 + 按口播时长定帧 + CSS 动画等待）
4. 实现帧序列 FFmpeg 合成
5. 实现 Playwright 不可用降级（现有渲染管线回退）
6. 补测试（Playwright 可用/不可用两路径）
7. 门禁全绿：pytest / ruff / mypy
8. commit+push 到卡内分支 `codex/xy056-frame-renderer`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

- 任一样片（HTML 场景）经帧渲染器出片成功，质量量化达标（复用 xy-plan-006 check_video_quality 标准）
- 模拟 Playwright 不可用（如设环境开关/断依赖），管线自动降级现有渲染，出片不中断
- 帧数=口播时长×30fps（±容差），CSS 动画已执行（截帧含动画终态）
- 未改动 `src/xianyu/` 及非 scene 的 pipeline 文件
- pytest 新增测试通过，ruff/mypy 无新增告警

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：`pytest tests/ -q`
编译：`python3 -m compileall video-pipeline/`
lint：`ruff check video-pipeline/`
类型：`mypy video-pipeline/`（以仓库实际 mypy 配置为准，无新增错误）
范围：false

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成 维护区 四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 机审区；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：（回写时填）

### 实现说明

（回写时填：改动点与文件）

### 测试结果

（回写时填：门禁命令逐条结果）

### push 证据

（回写时填：commit hash + 分支名）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[x]
   - 说明：已同步，实现了 xy-plan-008 中的 5.1 Playwright 帧渲染器，合拢了 HTML 场景到视频的主链路。
2. **教训沉淀**：本卡是否产出可复用教训？[x]
   - 说明：沉淀了离线环境下 CDN 加载 gsap 延迟超时导致 EPIPE 错误的教训，已通过本地复制和引用 gsap.min.js 的方式彻底解决。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[x]
   - 说明：新增了 `stages/scene/frame_capture.py` 和 `stages/scene/html_composer.py`，未改变原有项目的目录结构与路径。
4. **线路图**：项目近况/下一步是否变化？[x]
   - 说明：下一步可以继续并行开发 M6 展示台等其他管线优化和集成任务。

## 机审区

（机审方填写）

## 执行提示

- 项目：xy（Mac2017 上的 xianyu 独立业务仓；Python 视频/图文生产管线，经 CCC 出卡驱动开发。）

- 项目仓（只读参考）：/Users/fan/program/apps/xianyu（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要（xy-plan-008 M5 视频高表现力二期·功能卡 5.1 Playwright 帧渲染器）：HTML 场景→帧→视频。验收：任一样片经帧渲染器出片且质量量化达标；模拟 Playwright 不可用验证降级路径。依赖：无（承接已落地 Hyperframes），可立即启动。

- 项目线路/近况：
  - 50 张卡（xy001-051）全部关闭；M1 视频里程碑 / M2 生产就绪 / M3 高表现力全部完成
  - **2026-08-20 新里程碑**：M5 高表现力二期（本卡所在）/ M6 前端展示台 / M7 发布闭环（等 Cookie）
  - M6 进度：xy052/xy053/xy054 已关闭，xy055 待分派；本卡可与 M6 卡并行开发
  - M3 已落地：视觉模板库（xy-plan-005）、质量量化（xy-plan-006）、渲染引擎升级（xy-plan-007，Hyperframes + PIL 线程池回退 + glass-card/dark-tech）
  - html_scene 骨架已有（agent/schema/renderer）；`frame_capture.py`/`html_composer.py` 尚不存在——本卡补上

- 开发技能与命令：
  - 运行测试：`pytest tests/ -q`（repo 根）
  - 代码检查：`ruff check video-pipeline/`；类型：`mypy video-pipeline/`
  - Playwright 环境：`pip install playwright && playwright install chromium`（2017 上验证）

- 历史教训（避免踩坑）：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **适用场景**：pipeline 路径/依赖变更
  - 降级路径先于主路径实现：Playwright 缺失时生产链路不能被拖死（历史教训：依赖缺失导致生产阻塞）
  - 只读红线：admin 适配层职责是「包装数据成 JSON」——本卡不涉及 admin；读状态/渲染入口前先确认现有 scene 渲染现状（勿假设旧定义）

- 禁区：- 前缀是 `xy`；卡文件名必须 `xyNNN-…`
- 禁止在 CCC 建业务深文档目录

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：xy（Mac2017 上的 xianyu 独立业务仓；Python 视频/图文生产管线，经 CCC 出卡驱动开发。）

- 审查清单：
  - 降级路径完整（Playwright 不可用 → 现有管线回退，生产不中断）
  - 只动 video-pipeline/stages/scene/，未改 src/xianyu/ 与其他 stage
  - 帧数计算与口播时长一致（30fps），CSS 动画等待实现正确
  - 测试覆盖 Playwright 可用/不可用两路径

- 历史教训（审查时重点关注）：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **适用场景**：pipeline 路径/依赖变更

- 架构约束/红线：- 前缀是 `xy`；卡文件名必须 `xyNNN-…`
- 禁止在 CCC 建业务深文档目录

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。