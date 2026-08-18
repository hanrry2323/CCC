# 方案 · LLMProvider 本地 Ollama ↔ 在线 API 配置层（M4-4.1）

> 项目：cla · 编号：cla-plan-009 · 状态：部分执行 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-18（cla018 已回写待合入）
> 关联卡：cla018
> 关联方案：无
> 进度：0/1 (0%)
> 里程碑：M4 · 双轨决策与话术自动生成
> 子项目：4.1 LLMProvider 本地 Ollama ↔ 在线 API 配置层
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

建立 LLM 统一调用层：本地 Ollama 与在线 API 双轨可切换（配置驱动），带失败降级与用量控制，供 4.2 机会挖掘与话术生成、5.1 合规初审共用。

## 背景

架构定稿：
- `src/llm/provider.py`：LLMProvider 抽象基类 + `OllamaProvider`（`http://localhost:11434`）+ `OnlineProvider`（兼容 OpenAI SDK 格式）。
- 配置：settings.yaml 中 `llm.mode: ollama|online`，`llm.ollama_model`、`llm.online_model`、API Key 走 secure_keys.env。
- 降级：online 不可用 → 自动降级 ollama（或反之，配置决定）；超时与重试次数配置化。
- 用量控制：在线 API 每任务 token 上限 + 日调用上限（防费用失控）。

## 方案内容

### 1. LLMProvider 双轨实现
- `src/llm/provider.py`：基类（chat(messages) → str 契约）+ OllamaProvider + OnlineProvider。
- 统一异常语义：LLMUnavailableError（触发降级）、LLMTimeoutError（重试）。

### 2. 配置与降级
- settings.yaml + secure_keys.env 双轨配置；provider 工厂函数按 mode 装配。
- 降级链：主 provider 失败 N 次 → 切换备用 → 仍失败则任务打 failed 标签（不静默丢任务）。

## 验收标准

- [ ] ollama 模式本地跑通 chat
- [ ] online 模式 mock 验证
- [ ] 主 provider 故障自动降级且任务不静默丢失
- [ ] token 上限/日上限生效

## 功能卡

### LLM 双轨 Provider + 降级与用量控制

目标：完成 LLM 双轨调用层，交付可验收产物。

实现：按「方案内容」两节落地——provider.py 双轨 + 配置降级链。

验收：验收标准四条款全过（双轨跑通 / 降级 / 不丢任务 / 用量控制）。

颗粒度：子项目级（1 卡，约 2 天）。

依赖：无（可独立开发，与采集线并行）

架构位置：`src/llm/provider.py`、`config/settings.yaml`、`config/secure_keys.env`

## 转卡计划

LLM 双轨 Provider（1 卡，待出卡）

## 备注

- 本卡可独立先行（不依赖 M2/M3 数据），与采集线并行开发。
- 在线 API 优先兼容 OpenAI SDK 协议（含本地中转站 6102 亦可作为 OpenAI 兼容端点）。