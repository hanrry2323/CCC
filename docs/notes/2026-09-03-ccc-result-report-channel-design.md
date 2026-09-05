# CCC 执行结果上报通道设计稿（C 方向，二期输入）

> 状态：阶段一已实施 2026-09-05，阶段二=看板前端合成视图
> 日期：2026-09-03
> 背景：A1/A2 已将执行体结果文件与引擎代写卡分离；本稿讨论未来看板 API 上报，不改变当前单写者链。

## 1. 目标

为执行体提供一个受鉴权保护的结果上报入口，使看板能实时展示执行进度；卡文件仍由 Engine 唯一写者维护，API 上报不直接改卡文件。

## 2. 建议接口（未实施）

```text
POST /api/v1/board/result
Authorization: Bearer <短期 token>
Content-Type: application/json

{
  "work_id": "tst904",
  "event": "executor_started|executor_completed|executor_failed|executor_suspended",
  "payload": {
    "executor_rc": 0,
    "card_title": "smoke: A1-A2 full-probe",
    "result_path": "<逻辑标识，不传本机绝对路径>",
    "duration_s": 166,
    "probe_status": "pass|fail|unknown",
    "selftest_status": "pass|fail|unknown",
    "maintenance": {
      "plan_sync": "yes|no",
      "lesson": "yes|no",
      "readme": "yes|no",
      "roadmap": "yes|no"
    }
  }
}
```

## 3. 写入与消费边界

1. 执行体持短期 Bearer token POST 事件；服务端只做 schema 校验、鉴权、幂等写入运行时事件存储。
2. Engine 仍从 `log_dir/<work_id>-ccc-result.md` 读取权威结果，并负责主仓卡回写、状态迁移、commit+push。
3. 看板页面把 API 事件与卡文件/`runtime_state` 合成「执行中」视图；事件只能补充实时进度，不能覆盖卡文件终态。
4. `work_id + event + event_id` 做幂等键；过期、未知卡号、重复事件拒绝或无害丢弃。

## 4. 安全边界

- 上报端点必须走 Bearer token；token 只放请求头，不落日志/结果文件/卡正文。
- 不上报卡全文、DSH 原始输出全文、凭据、业务仓绝对路径；`result_path` 只用逻辑标识。
- work_id 必须经过卡存在性与项目权限校验，禁止路径拼接和路径穿越。
- payload 限制大小、字段枚举和字符串长度；服务端拒绝未知字段或按版本兼容策略处理。
- API 事件为观测数据，不能绕过 `card_gate`、状态机、机审或合入门禁。

## 5. 当前文件链迁移路径

```text
现行：
DSH worktree/.ccc-result.md
  → wrapper（退出后、worktree 清理前）
  → log_dir/<work_id>-ccc-result.md
  → Engine 收单代写主仓卡
  → origin/main + 看板索引

二期可选增强：
DSH wrapper 同步 POST /api/v1/board/result
  → 运行时事件存储（只读观测）
  → 看板执行一页视图

```

API 上报是旁路观测，不替代文件链；网络失败不能阻塞 Engine 收单，文件链仍是事实源。

## 6. 风险与迁移步骤

| 风险 | 处置 |
|---|---|
| token 泄露 | 短 TTL、仅 header、服务端不回显、不写日志 |
| 重复/乱序事件 | 幂等键 + 按事件时间/状态机过滤，终态不可回退 |
| API 与文件链不一致 | 页面显示来源与时间；文件链终态优先；后台对账报警 |
| 事件洪泛 | 单卡/单 token 速率限制与 payload 上限 |
| 迁移期间旧 wrapper | API 可选能力探测；缺失时纯文件链继续工作 |
| 事件存储成为第二事实源 | 明确只存观测事件，卡状态只认卡文件 + Engine runtime |

实施顺序：先定义 schema/鉴权/幂等测试 → 增加只读事件存储 → 看板读取与对账 → 最后 wrapper 可选上报；每步单独验收。

## 7. 验收输入（未来实施时）

- 合法 token + 合法事件返回 2xx，重复事件幂等。
- 无 token、错误 token、未知 work_id、超大 payload、路径穿越字段均拒绝。
- API 不可达时，`.ccc-result.md` 文件链仍可完成 Engine 收单。
- 看板逐卡展示：卡号、事件时间、执行体、结果状态、回写状态、门禁结果；终态与卡文件一致。
