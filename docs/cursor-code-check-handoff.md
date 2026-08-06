# CCC 全项目代码检查交接文档（给 Cursor · 2026-08-06）

> 用途：让 Cursor 熟悉 CCC 项目现状后，执行一次全项目代码 bug 检查。先读本文 + 仓库根 `CURSOR.md` + `docs/INDEX.md` §0 + `docs/dispatch/T48-audit-report.md`。

## 一、项目现状（重启后基线）

- **版本**：v0.70.0；main = `fecbe4e`（2026-08-05 新栈对齐收口）
- **架构**：薄驱动 Engine + Markdown 任务卡（`docs/dispatch/TNN-*.md` 唯一事实源）+ 看板/HTTP/桌面双壳；生产在 Mac2017（:7788 + 中继 6100/6102），M1 是开发副本
- **流程**：Codex 出卡 → Engine 派发 Claude Code（2017 worktree）→ 分步提交 → Codex 验收 → 合入部署
- **执行体**：日常 = OpenCode / Claude Code（注册表可后台 CLI）；**Cursor = 难度开发突击手**（硬骨头 / 复杂排查 / 点名硬任务）
- **看板**：74 已关闭 / 0 待分派 / 4 历史打回；今天（08-05）T54-T69 全链路闭环部署

## 二、代码结构地图

```
server/
├── engine/   薄驱动编排：main.py（扫描/派发/收单/续作）dispatch.py（决策/构建命令）store.py（卡头状态机）
├── board/    看板派生：loader.py（扫描卡+增量索引）queries.py（三视图）validate.py（卡头门禁）export.py
├── web/      HTTP 壳：server.py（API+静态托管）brain.py（对话大脑→2017 Claude）legacy-chat/（前端 SPA）
├── kb/       知识库：indexer/search（BM25）、mcp_server
├── config/   config.env / executors.json（执行体注册表）
└── tests/    单测（pytest）

desktop/
└── Sources/CCCDesktop/   macOS SwiftUI 壳（APIClient/AppModel/BoardView/TaskCardPanel/OpsView/ContentView…）

deploy/       release.sh（一键放行，含 Engine plist 自愈）nginx/（模板）
scripts/      new-card.sh / verify-shell.sh 等少量工具（旧 scripts/ 已归档，勿按旧文档行事）
docs/         权威文档 + dispatch/（任务卡）+ archive/（归档，勿改）
```

## 三、已知问题清单（检查时优先对照，勿重复发明）

| # | 已知问题 | 状态 |
|---|---|---|
| 1 | M1→2017 静态资源并发加载 ERR_CONNECTION_RESET（41% 实测），SPA 白屏——前端已 T68 兜底（bootloader 重试+降级），网络根因未修 | 待整体联调 |
| 2 | 免登录模式下标题栏仍显示「未登录」+「退出」按钮（误导文案） | 待修 |
| 3 | 大脑报「77 张任务卡」vs validate/看板「76 张」口径不一致 | 待核 |
| 4 | 2017 plist 自愈 DATA_DIR fallback 与真实 `~/.ccc/data` 不一致（T69 备注） | 低优先 |
| 5 | Nginx 模板就绪但 2017 未实际安装（brew formula DSL 报错） | 待修 |

## 四、本次检查任务（T70 · 全项目代码 bug 检查）

### 范围（只读检查 + 测试运行）

1. `server/`：engine（派发/收单/续作/并发）、board（loader/validate/queries）、web（server.py 路由/静态/鉴权、brain.py 大脑调用）、kb（索引/搜索）
2. `desktop/Sources/CCCDesktop/`：Swift 壳（网络层、状态管理、视图刷新、并发/actor）
3. `server/web/legacy-chat/` 前端：JS（消息流/SSE/工具卡/卡流/看板/路由）、CSS 布局

### 检查维度（每条问题必须有证据）

- **正确性 bug**：逻辑错误、边界条件、空值/类型、竞态/并发、异常未处理、资源泄漏（线程/连接/文件句柄）、死代码/不可达分支
- **一致性**：前端 vs 后端契约（字段名/状态值/接口路径）、双壳（HTTP vs 桌面）行为差异
- **健壮性**：超时/重试/降级缺失、错误信息怼用户、无限加载、轮询风暴
- **安全**（低优先）：路径拼接、密钥泄露、未授权端点

### 交付物

问题清单文档 `docs/dispatch/T70-audit-report.md`（或回写区完整列出），每条含：
`编号 / 位置（文件:行）/ 现象（一句话）/ 复现或证据（命令输出/测试/代码引用）/ 影响 / 严重级 P0-P3 / 修复建议`

- **不少于 15 条**；P0=会导致错误结果或崩溃，P1=明显功能缺陷，P2=健壮性/体验，P3=可后置
- 禁止把「风格偏好/代码风格」当 bug；每条必须用户可感知或影响正确性/一致性
- 附验证证据：pytest 全量输出、swift build/test 输出（如环境允许）、无头走查日志（如做）

### 红线

1. **只读检查，不擅自改代码**（修复走正式任务卡）；可写的问题清单文档除外
2. 只检查 `/Users/apple/program/CCC` 开发副本；**禁止 SSH 改 2017 生产**
3. 不碰 QuantHive / qb（双轨独立）；不碰 docs/archive/（归档）
4. 不伪造证据——每条问题给真实命令输出或代码引用
5. 分支 `codex/cursor-t02-code-audit`（从 main 新建），分步提交，push 后等 Codex 验收

## 五、验收标准（Codex 独立复核）

1. 清单 ≥15 条且条条有位置 + 证据 + 严重级 + 修复建议
2. 至少覆盖 server/ 与 前端 两大块；desktop 有结论（要么查了要么说明受限原因）
3. 与已知问题清单（§三）不重复编造；发现的已知问题可标记「已登记」引用编号
4. pytest 全量跑一遍（2017 或本机，记录真实输出）；能补跑 swift build/test 更好
5. 分支提交干净、push 成功
