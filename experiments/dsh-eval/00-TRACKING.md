# DSH 实验追踪表（25 开放实验）

> 计划依据：`qx-map __archive__/research/dsh-eval-report-2026-08-16.md` 维度十 + 本分支执行计划。
> 主序：安全优先。状态：🔲计划 / 🚧进行中 / ✅完成 / ⚠️挂账。批次推进，每批结束简报。
> 更新：2026-08-16

## 批次总览

| 批次 | 主题 | 实验 | 状态 |
|---|---|---|---|
| B0 | 环境冒烟 | 测试实例 run_code 全链路 + 隔离 | 🚧 |
| B1 | 安全（A组） | A1 worker 逃逸 / A2 escalation / A3 workflow-vm | ✅ |
| B2 | 链路（B组） | B4 seq582 / B5 超时 / B6 车道 / B7 MCP白名单 | 🔲 |
| B3 | 模式（C组） | C8 fork工具集 / C9 both路径 / C10 python flavor | ✅ |
| B4 | 会话（D组） | D11 pruner+compaction / D12 KV / D13 title / D14 spill / D15 并发 | ✅ |
| B5 | 多代理（E组） | E16 递归 / E17 冷恢复 / E18 fork上下文 / E19 patch / E20 IPv6 / E21 凭证 / E22 续写 | ✅（3挂账） |
| B6 | 模型（F组） | F23 漏参率 / F24 sandbox-exec / F25 下行协议 | 🔲 |

## 实验明细

### B0 · 环境冒烟
| ID | 内容 | 状态 | 结果链接 |
|---|---|---|---|
| B0 | 测试实例 code 模式跑通 + code-dispatch 落日志 + 生产 web 隔离 | ✅ | notes/00-smoke.md |

### B1 · 安全（优先）
| ID | 内容 | 状态 | 结果链接 |
|---|---|---|---|
| A1 | worker 逃逸触达面枚举（getBuiltinModule 全量 + 宿主内存态） | ✅ | notes/01-a1-worker-escape.md |
| A2 | escalation allowed-once 多轮语义端到端 | ✅（部分） | notes/02-a2-escalation.md |
| A3 | workflow vm 逃逸范围 | ✅ | notes/03-a3-workflow-vm.md |

### B2 · 链路
| ID | 内容 | 状态 | 结果链接 |
|---|---|---|---|
| B4 | seq582 矛盾单点收口（带 desc 仍报缺的复现与解释） | 🔲 | notes/04-b4-seq582.md |
| B5 | run_code 内层工具 30s 超时可配置性 | 🔲 | notes/05-b5-timeout.md |
| B6 | Promise.all 与车道启动交互、commit 背压 | 🔲 | notes/06-b6-lanes.md |
| B7 | MCP 参数白名单（schema 外键透传/收紧） | 🔲 | notes/07-b7-mcp-params.md |

### B3 · 模式
| ID | 内容 | 状态 | 结果链接 |
|---|---|---|---|
| C8 | fork 子代 wire 工具集继承 | ✅（源码） | notes/08-c8-fork-tools.md |
| C9 | both 模式实际调用路径 | ✅ | notes/09-c9-both-mode.md |
| C10 | python flavor 实测 | ✅（不可用） | notes/10-c10-python-flavor.md |

### B4 · 会话
| ID | 内容 | 状态 | 结果链接 |
|---|---|---|---|
| D11 | pruner 与 compaction 叠加行为 | ✅ | notes/11-d11-pruner-compaction.md |
| D12 | KV 缓存复用收益量化 | ✅（机制） | notes/12-d12-kv-cache.md |
| D13 | session-title 双 provider 并发语义 | ✅ | notes/13-d13-session-title.md |
| D14 | spill 在 web profile 是否生效 | ✅（未启用） | notes/14-d14-spill.md |
| D15 | headless 与 web 共享存储并发冲突 | ✅ | notes/15-d15-storage-concurrency.md |

### B5 · 多代理
| ID | 内容 | 状态 | 结果链接 |
|---|---|---|---|
| E16 | workflow 无限递归（无 maxDepth 实测） | ⚠️挂账 | notes/16-e16-workflow-recursion.md |
| E17 | 连续式子代理冷恢复端到端 | ⚠️挂账 | notes/17-e17-subagent-cold-recover.md |
| E18 | fork 中途上下文缺失 | ⚠️挂账 | notes/18-e18-fork-context.md |
| E19 | patch `-id: dsh-web-app` 静默 no-op 终判 | ✅ | notes/19-e19-patch-noop.md |
| E20 | headless IPv6 残余 | ✅ | notes/20-e20-ipv6.md |
| E21 | web-search credentials 持久化 | ✅（源码） | notes/21-e21-websearch-creds.md |
| E22 | max-tokens 截断续写方案评估 | ✅（机制） | notes/22-e22-max-tokens.md |

### B6 · 模型
| ID | 内容 | 状态 | 结果链接 |
|---|---|---|---|
| F23 | description 漏参率 × 模型/effort 对比 | 🔲 | notes/23-f23-description-rate.md |
| F24 | sandbox-exec 废弃节奏 + bwrap 迁移评估 | 🔲 | notes/24-f24-sandbox-exec.md |
| F25 | 生产下行协议确认（WS vs SSE） | 🔲 | notes/25-f25-downlink.md |
