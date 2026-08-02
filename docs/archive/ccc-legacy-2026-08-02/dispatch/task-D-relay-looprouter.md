# 任务书 D · relay → M1 loop-router 迁移收尾（窗口 D）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 D 即可。

## 0. 先读

1. `CLAUDE.md`
2. `docs/relay/`、`docs/ccc-hub-ports.md`、`docs/architecture-core.md`
3. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 背景（一句话）

`relay/` 目录已删除，CCC 全部出口统一走 M1 ai-loop-router（:4100/:4102），sidecar 已切 4100。剩下 CCC 仓内残留引用与文档不一致需要收尾。

## 2. 任务目标

1. 全仓扫残留：`:4000`、`ccc-relay`、relay 域引用（代码 / launchd / 配置 / 文档 / 测试断言 / agent-mind）
2. 分类处置：真残留 → 修；白名单/历史备份 → 标注不动的理由
3. 端口权威表统一：docs 与配置以 4100/4102 为准
4. 迁移回归：代理链路冒烟（chat / 流式 / 工具调用）与相关测试补强

## 3. 允许范围

- CCC 仓内与迁移相关文件：scripts 下端口/launchd/配置/agent-mind、docs、测试断言
- 不在此窗口动业务逻辑

## 4. 红线（禁止）

- **ai-loop-router 仓库本体**（独立仓，本窗口禁止；发现问题记入报告即可）
- 网页前端、`desktop/`、`src-tauri/`
- 引擎业务逻辑与状态机
- 启动/重启产线进程（只做配置与测试）
- 提交 main

## 5. 流程（spec-first 门）

第一轮：`/plan` 输出「残留清单 + 分类表（真残留 / 白名单 / 历史）」，**只读不改**。  
确认后修复并回归。

## 6. 验收标准

- 白名单外全仓无 `:4000` / `ccc-relay` / relay 域残留（贴 grep 证据）
- 端口权威表与代码一致
- 相关测试全绿；冒烟链路通（chat / 流式）
- 报告标注每处「改 / 保留」的理由
