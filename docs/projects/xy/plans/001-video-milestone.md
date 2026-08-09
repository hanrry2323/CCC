# 方案 · xianyu 视频里程碑推进

> 项目：xy · 编号：xy-plan-001 · 状态：已完成 · 作者：老板 · 工具：Codex
> 创建：2026-08-03 · 更新：2026-08-10
> 关联卡：xy001, xy002, xy003, xy004, xy005, xy006, xy007, xy008, xy009, xy010, xy011, xy012, xy013, xy014, xy015, xy016, xy017, xy018, xy019, xy020, xy021, xy022, xy023, xy025, xy026, xy027, xy028, xy029, xy030, xy031
> 关联方案：无
> 迁移自：qx-map `__archive__/decisions/xianyu-视频里程碑-方案-2026-08-03.md`
> 决策人：老板 · 记录/管理：Codex · 执行：Trae · 验收：Codex
> 状态：✅ 已完成
> 关联：`command-post/intents.md`（INT-122）
> 性质：xianyu 视频推进唯一执行依据；与旧文档冲突处，以本方案为准。

## 一、背景与诊断（2026-08-03 实测）

| 项 | 实测值 | 判断 |
|----|--------|------|
| 代码完成度 | v2 平台 11/11 段完成（D0-D8.1），含视频端到端、MPT 桥、SAU 桥 | 框架完整 |
| 运行面 | 8765 / 8080 / 5409 三端口全部不可达，launchd 无 xianyu 服务注册 | 服务当前全停 |
| 数据面 | SQLite 6 表全空（topics/articles/publish_logs/cookies/daily_stats 等 0 行） | 从未真业务运行 |
| 测试基线 | 428 passed / 232 failed / 10 skipped | 失败主因 = venv 缺 pytest-asyncio（环境问题，非代码腐化） |
| 视频真路径 | `video-pipeline/`（script→scene→tts→subtitle→compose 五阶段）；老 `src/xianyu/video/` 为历史旁路 | 生产走 video-pipeline |
| 质量一期 | 已交付：码率 0.12→3.7 Mbps、文件 4.72→26.52 MB（量化 ×5.6），A1-A6 全达 | 基础质量已达标 |
| 模型通道（v2 实测） | mac2017 本机 opencode 1.17.13 已配 `loop/flash` → 6102 中转站（CCC 体系）；curl 实测 6-7s 返回、支持流式/tools、实际调度 deepseek-v4-flash | 通道可用，复用 CCC 基建 |
| 高质量种子 | `video-pipeline/hyperframes/`（HeyGen HTML 组合渲染工程，含 5 段样片）+ `video-pipeline/remotion/`（React 骨架） | 已埋两条升级路线 |
| 本机环境 | node v22.16 / npm 10.8 / ffmpeg 8.1 / hyperframes CLI 0.7.89 均可用 | 渲染环境齐备 |
| MPT | NAS 192.168.3.131:18080 不可达 | 外部依赖已失效，本轮不依赖 |
| 社区标杆 | MoneyPrinterTurbo 10 万星（xianyu 桥接上游）、ShortGPT 7.7k 星（频道自动化） | 有成熟可借鉴 |

## 二、终态一句话

xianyu = 一条命令从「话题」产出高质量竖屏视频、自动分发多平台的内容平台；本轮里程碑 = **用 HyperFrames 渲染引擎产出达到 MoneyPrinterTurbo 质量水平的竖屏视频样片**。

## 三、目标（3 个里程碑）

### M1 环境恢复 + 基线绿（本周）
- 修复 venv 依赖（补 pytest-asyncio 等 dev 包），全量测试恢复绿色基线
- 恢复 admin API / 静态前端可启动（8765/8080）
- 跑通 `video-pipeline` 产出 1 条 60-80s 1080×1920 竖屏视频（含 TTS 配音 + 字幕 + BGM）
- 验收：pytest 绿 + 1 条成品视频可播放

### M2 高质量视频样片（核心里程碑，2 周）
- 以 HyperFrames 为渲染引擎，建 3 套视觉模板（技术科普 / 财经解读 / 口播故事）
- 量化达标：码率 ≥3.5 Mbps、文件 ≥9 MB、时长 60-90s、分辨率 1080×1920、含配音/字幕/BGM/动态镜头
- 主观达标：老板抽检 3 条样片，视觉无廉价感（镜头运动 + 转场 + 字幕样式达标）
- 验收：3 条样片交付 + 对比 MoneyPrinterTurbo 默认产出

### M3 规模化生产 + 分发闭环（后续）
- 模板参数化（话题→文案→镜头→TTS→BGM 全自动）
- 批量生产（每日定时）+ SAU 分发接入（Cookie 就绪后）
- 验收：日产出 3 条视频 + 至少 1 平台真实发布

## 四、技术定案

| 项 | 定案 | 理由 |
|----|------|------|
| 渲染引擎 | **HyperFrames（主）** | 本机技能栈齐全、确定性渲染、已埋工程种子、质量上限远高于 ffmpeg 拼贴 |
| 备选引擎 | Remotion | 已埋骨架，复杂数据可视化/交互场景备用 |
| TTS | edge-tts（已有） | 多中文音色、零成本、已集成 |
| 字幕 | TTS 词边界 / 转录兜底 | video-pipeline 已有阶段，补齐即可 |
| BGM | 本地素材库 | 零成本，规避版权 |
| 内容生成 | **OpenCode flash 通道（6102，复用 CCC）**，轻量 HTTP 客户端直连 `http://127.0.0.1:6102/v1/chat/completions`（model=flash）；`opencode run --model loop/flash` 为 CCC 生产形态备选 | 零新成本、质量远超 7b、纯本地链路（mac2017→6102） |
| 社区借鉴 | MoneyPrinterTurbo 流水线（主题→脚本→素材→字幕→BGM→合成）；ShortGPT 频道自动化编排 | 直接对标已验证架构 |

**红线调整（老板已授权 2026-08-03）**：
1. **取消 Ollama 方案**（老板 v2 指令）：内容生成弃用 hp:11434 Ollama，改用 mac2017 已配置的 OpenCode flash 通道（6102，CCC 体系复用）。
2. 原「暂不接入 AI 视频 API」（2026-07-06 决策）→ 调整为「本地渲染为主；AI 视频 API 列为备选，接入须老板确认成本」。
3. 原「禁止引入未授权新依赖」（全局红线）→ 本任务范围授权 dev 依赖修复（pytest-asyncio 等）；新增运行时依赖须在方案列明。
4. 术语修正：机器别名 **feiniu → hp**（192.168.3.131，feiniu 机器已重装为 hp 节点），本次已同步 AGENTS.md + 归档决策；xianyu 仓内引用列入 Trae 任务卡。
5. 保留不动：凭证/密钥明文红线、硬编码凭据红线、`data/`/`logs/`/`.env`/`*.db` 不入库红线、`git add -A` 禁令、Mac2017 路径权威。

## 五、执行阶段（Trae 按序执行，Codex 阶段验收）

### P1 环境恢复（M1）
1. venv 修复：补 dev 依赖（pytest-asyncio 等），确认 pyproject.toml dev 组完整。
2. 恢复测试基线：`pytest tests/ -q --ignore=tests/e2e --ignore=tests/scripts` 全绿（修复环境性失败，不修业务）。
3. 启动服务：admin 8765 + web 8080 可访问 `/api/health`。
4. **OpenCode flash 接入**：在 `video-pipeline/stages/script/generator.py` 增加脚本生成后端 = 调用 `http://127.0.0.1:6102/v1/chat/completions`（model=flash，复用 CCC 6102 通道），失败回落现有模板拼装；另验证 `opencode run --model loop/flash` 形态（CCC 生产方式），两者取可用者。
5. **名称修正**：xianyu 仓内全部 `feiniu` → `hp`（含 `src/xianyu/bridge/mpt_bridge.py` 注释与文档）。
6. 跑通 `video-pipeline`：用现有 config 产出 1 条成品视频，验证输出目录结构。

### P2 高质量样片（M2）
1. 在 `video-pipeline/hyperframes/` 基础上建 3 套模板（tech / finance / storytelling），每套含镜头运动 + 转场 + 字幕样式。
2. 编码参数沿用质量一期已验证参数（high 4.2 / slow / CRF 21 / 3.5Mbps / AAC 192k）。
3. 产出 3 条样片并自检量化指标（ffprobe 取证）。

### P3 规模化（M3，本方案仅定目标，任务另行出卡）
1. 模板参数化 + 批量生产脚本。
2. SAU 分发接入（Cookie 由老板提供后）。

## 六、验收标准（Codex 独立取证）

1. P1：`pytest` 绿（无环境性失败）；`/api/health` 200；6102 flash 通道实测生成脚本成功（curl/脚本调用，6-7s 返回）；`video-pipeline/output/final.mp4` 存在且可播放。
2. P2：3 条样片 ffprobe 达标（码率/时长/分辨率）；老板抽检认可。
3. 交付：每阶段 commit message 附 Verification 摘要（per AGENTS.md §7）。

## 七、Trae 开发指令（M1，可直接转发）

```
【任务】xianyu 视频平台 M1：环境恢复 + 基线绿 + OpenCode flash 接入（Codex 出卡，Trae 执行）
【项目】/Users/fan/program/apps/xianyu（Mac2017 权威；本机可直读）
【红线】不碰 .env/密钥/data/*.db；不 git add -A；只 stage 本任务文件；不引入运行时新依赖；不修改业务逻辑。术语：hp=192.168.3.131（原名 feiniu 已废弃）。
【步骤】
1. venv 修复：检查 .venv 缺哪些 dev 依赖（重点 pytest-asyncio），补齐后确认 `pytest tests/ -q --ignore=tests/e2e --ignore=tests/scripts` 全绿；若 pyproject.toml dev 组缺失依赖，补齐并提交。
2. 服务启动：确认 admin/start.sh 或对应 launchd plist 可拉起 8765/8080，`curl http://localhost:8765/api/health` 返回 200。
3. OpenCode flash 脚本接入：`video-pipeline/stages/script/generator.py` 增加后端 = HTTP 调 `http://127.0.0.1:6102/v1/chat/completions`（model=flash，Bearer sk-noauth），输出严格 JSON（3 幕/每幕带 text+duration），失败回落模板拼装；先 curl 直连验证再改代码。
4. 名称修正：仓内全部 `feiniu` → `hp`（含 src/xianyu/bridge/mpt_bridge.py 注释与 README/文档）。
5. video-pipeline 试跑：用现有 config.json 跑通，产出 output/final.mp4（60-80s，1080×1920），ffprobe 记录码率/时长/分辨率。
6. 每步留证据：命令输出、ffprobe 摘要写入 commit message Verification 段。
【验收】pytest 绿 + /api/health 200 + flash 脚本生成实测成功 + 1 条成品视频。
【提交】前缀 feat:/fix:/chore:，只 stage 相关文件。
```

## 八、v2 修订说明（2026-08-03 老板指令）

1. **取消 Ollama**：内容生成不再依赖 hp:11434 Ollama（7b 仅 3.7 tok/s，速度/质量均不达标）。
2. **改用 OpenCode flash**：mac2017 已配置（opencode **1.18.11** → loop/flash → 6102），复用 CCC 基建。实测 `opencode run --model loop/flash` 正常返回（9s）、6102 通道质量合格。**2026-08-03 修复根因**：opencode 1.18 实际读取 `~/.opencode/opencode.json`（旧 4002 退役配置），旧 `~/.config/opencode/` 未生效导致 CLI 挂起；已清理旧配置并将 `~/.opencode/` + `~/.config/opencode/` 均重写为 6102 flash，实测打通。
3. **名称修正**：feiniu → hp（本方案及 qx-map 归档、~/.Codex/AGENTS.md 已同步；xianyu 仓由 Trae 修正）。

## 九、备注

- 本方案不涉及 xianyu 业务代码修改决策；P1-P2 为开发执行，交由 Trae。
- Codex 负责每阶段验收取证；老板负责样片主观抽检。
- M3 目标已定，任务卡在 M2 验收后另行派发。
