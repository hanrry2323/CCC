# 任务书 I · 7788 对话壳体验优化（窗口 1）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 1 即可。  
> 依据：`docs/dispatch/2026-08-01-http-chat-optimization-review.md` 第一批「对话」部分。

## 0. 先读

1. `CLAUDE.md`
2. `docs/dispatch/2026-08-01-http-chat-optimization-review.md`
3. 现有对话实现：`frontend/js/components/message.js`、`composer.js`、`streamRegistry.js`、`api.js`
4. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 任务目标（对话壳「感知层」）

1. **断连横幅**：对话中请求失败 / sidecar 不可达 → 顶部横幅「连接中断，正在重连…」，恢复后自动消失；不打断消息流、不弹裸错误
2. **模型档位异常提示**：`/health` 拉不到或 models 为空 → 输入区上方提示 + 明确警告；恢复后自动消除
3. **流式细节**：流式首包长时间无响应有感知提示（如「等待模型响应…」超时态）；流式中切换 tab 不丢状态（验证 streamRegistry 现状，缺则补）
4. **测试**：以上行为补结构锁 / 纯函数测试（沿用 `scripts/tests/test_web_*` 基建）

## 2. 允许范围

- `scripts/chat_server/frontend/` 下 chat 域：`js/components/message.js`、`composer.js`、`streamRegistry.js`、`api.js`、`app.js`、`js/state.js`、相关 CSS（components.css / variables.css 的 chat 区块）、对应测试

## 3. 红线（禁止）

- **看板/运维页面逻辑不动**（窗口 2 的活）；后端零改动
- 4000/4100 relay 相关、DRY_RUN、产线启动
- 不破坏 Desktop/sidecar 对话链路（7788 主链路回归必须绿）
- 不删文件（除非计划说明）；提交 main 禁止

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「三项感知能力设计 + 涉及文件清单（明确不与窗口 2 重叠）+ 测试方案」，**不写代码**。  
确认后实现，测试全绿再提交。

## 5. 验收标准

- 断连横幅：触发/恢复有测试或结构锁；不阻断消息流
- 模型档位异常：/health 失败或空 models 有提示；恢复自动消
- 流式首包慢有提示；切 tab 状态不丢（有验证）
- 对话主链路回归通过；提交在 `codex/ws-7-chat-ux` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 移交项
