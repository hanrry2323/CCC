# 任务卡 xy006 · 平台适配：接入快手与微信视频号发布通道（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

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

## 回写区

**执行体**：OpenCode · 日期：
