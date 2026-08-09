# 任务卡 xy006 · 平台适配：接入快手与微信视频号发布通道（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

将快手（kuaishou）与微信视频号（channels）发布通道接入 `sau_bridge.py`，打通 xianyu 到 `social-auto-upload`（sau_backend）的数据发布，消除目前在 GOAL.md 中「待 PoC 接入」的挂账状态。

## 红线（先看）

1. 只动 xianyu 仓中发布网桥与平台适配逻辑（如 `src/xianyu/bridge/sau_bridge.py`）；不触碰 2017 的外部服务，不重构 `social-auto-upload` 项目本体。
2. 不直推 main；代码走卡内分支 `codex/xy006-platform-kuaishou-channels-bridge`。
3. 对快手/视频号的入参构建必须与 `sau_backend:5409` 接口协议严格一致。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- `src/xianyu/bridge/sau_bridge.py` 内部平台分发。
- 快手（kuaishou）与微信视频号（channels）的发布和账号状态核验逻辑。
- 视频发布入参 schema 扩展。

## 步骤

1. **调研协议**：通过只读方式阅读 `docs/09-部署方案/06-social-auto-upload部署方案.md` 或直接调用 `sau_backend` 账号列表 API，查看快手和视频号的 `platform_id` 及其所需字段（通常是 `title`, `tags`, `video_path`）。
2. **扩展网桥代码**：
   - 修改 `src/xianyu/bridge/sau_bridge.py`，增加对 `kuaishou` 和 `channels` 的支持。
   - 实现将 xianyu 的本地视频、选题标题、标签自动桥接到 SAU 接口参数。
   - 增加对快手和视频号 Cookie 状态 / 账号在线状态的健康度核对路由（对接 `normalize_platform_status`）。
3. **补齐单测**：
   - 编写 `tests/` 下对 `sau_bridge` 新平台的 mock 测试，模拟 `sau_backend` 响应，保证不依赖真实网络可过。
4. **探针自测**：
   - 命令输入：`python -m xianyu.cli publish --platform kuaishou --video test.mp4` 与 `channels`。
   - 确认网桥被触发，在 mock 或 debug 模式下输出了送往 SAU 5409 正确的 Payload。
5. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `sau_bridge.py` 成功接上 `kuaishou` 与 `channels` 平台映射，API 桥接完全合规。
2. 命令行或 API 调用快手/视频号发布时，能正确向 `sau_backend` 发起请求（附请求 payload 与 mock 响应）。
3. 扩展后的 `sau_bridge` 测试用例 100% 通过。

## 补充信息

- 业务价值：快手与视频号是最大的短视频流量阵地之一。目前 SAU 已经支持此二者，但 xianyu 却缺少对应发布网桥，导致一直处于待办。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 机审区

**机审方**：Claude Code · 日期：2026-08-07 · **机审：通过**

独立取证（读 git 对象 + 临时 worktree checkout `origin/codex/xy006-platform-kuaishou-channels-bridge@56a6262`，未改业务代码）：

1. **实现已 push**：commit `56a6262` 改 `sau_bridge.py`（+65：`channels:2` 映射、`check_platform_status`/`platform_status` action 路由）+ `test_sau_bridge.py`（+131：4 个 `test_xy006_*`）。未直推 main，合规。
2. **协议一致**：`docs/06-平台适配器/视频号.md` 确认视频号走 SAU 腾讯通道（type 2），`channels:2` 与 `tencent:2` 同值属有意设计。
3. **测试 100% 通过**：临时 checkout 远程分支运行，`tests/bridge/test_sau_bridge.py` 24/24 通过（含 `test_xy006_upload_video_channels_success` 验证 payload、`check_platform_status` kuaishou/channels 健康归一化）。
4. **只动 xianyu 仓**：改动均限 xianyu `src/`+`tests/`。

如实说明：kuaishou 发布桥接（type 4）main 分支已具备，本 commit 实质新增 = channels 发布通道 + 快手/视频号健康度核对路由；卡头达成，可进入人侧「合入批准」。

## 回写区

**执行体**：OpenCode · 日期：2026-08-07

### 1. 实现说明
- `src/xianyu/bridge/sau_bridge.py`：新增快手/视频号（channels）发布桥接——`channels:2` 平台映射、`check_platform_status` / `platform_status` action 路由（快手/视频号健康度归一化核对）；kuaishou（type 4）发布桥接 main 已具备，本卡实质新增 = channels 发布通道 + 双平台健康度核对路由。
- `tests/bridge/test_sau_bridge.py`：新增 4 个 `test_xy006_*` 用例，覆盖 channels 上传 payload、平台健康状态归一化。

### 2. 测试结果
- `tests/bridge/test_sau_bridge.py` **24/24 通过**（含 `test_xy006_upload_video_channels_success` 验证 payload）。

### 3. Push 证据
- **业务仓分支**：`codex/xy006-platform-kuaishou-channels-bridge`（@56a6262，2026-08-09 复核确认）
- **Commit Hash**：`56a6262`（`feat(sau_bridge): add support for kuaishou and channels publishing and health checks`；`src/xianyu/bridge/sau_bridge.py` +65、`tests/bridge/test_sau_bridge.py` +131）
