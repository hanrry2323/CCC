# Relay 引用清理计划：`:4000`/`:4002` → `:4100`/`:4102`

## 当前状态分析

通过全面浏览，24 个目标文件中**大部分已经完成更新**。以下是探索结果摘要：

### 已完成更新的文件（不需再改）

以下文件已确认引用已更新为 `:4100`/`:4102`：

| 文件 | 状态 |
|------|------|
| `docs/deploy/desktop.md` | ✅ 已更新（:4100/:4102） |
| `.ccc/infrastructure.md` | ✅ 已更新（:4100/:4102） |
| `docs/config.md` | ✅ 已更新（:4100） |
| `CLAUDE.md` | ✅ 已更新（:4100/:4102） |
| `docs/GLOSSARY.md` | ✅ 已更新（:4100/:4102） |
| `docs/deploy/server-layout.md` | ✅ 已更新（:4100/:4102） |
| `docs/executors/loop-code.md` | ✅ 已更新（:4100/:4102） |
| `docs/relay/DEPLOY-2017.md` | ✅ 已添加废弃说明，端口已更新 |
| `docs/lessons.md` | ✅ 已更新（:4100） |
| `templates/executor-prompt.template.md` | ✅ 已更新（:4100） |
| `templates/executor-prompt.README.md` | ✅ 已更新（:4100） |
| `templates/.ccc-profile.md` | ✅ 已更新（:4100） |
| `docs/ops/GO-LIVE-DESKTOP.md` | ✅ 已更新（:4100/:4102） |
| `docs/product/desktop-agent-sidecar.md` | ✅ 已更新（:4100/:4102） |
| `docs/product/desktop-connection.md` | ✅ 已更新（:4100/:4102） |
| `docs/product/dev-channel.md` | ✅ 已更新（:4100） |
| `docs/product/dialogue-orchestration-boundary.md` | ✅ 已更新（:4100/:4102） |
| `docs/briefs/2026-07-28-relay-flash-seal.md` | ✅ 已更新 |
| `docs/briefs/2026-07-27-golden-path-evidence.md` | ✅ 已更新 |
| `docs/briefs/2026-07-27-ccc-production-readiness.md` | ✅ 已更新 |
| `docs/releases/v0.62.0.md` | ✅ 已更新 |
| `references/examples/qxo-audit-frontend.md` | ✅ 已更新（:4100） |
| `docs/deploy/migration-m1-to-2017.md` | ✅ 已更新（:4100/:4102） |
| `docs/ccc-hub-ports.md` | ✅ 已更新（:4100/:4102） |

### 仍需处理的残留引用

通过 grep 确认，以下目标文件中仍有残留的旧引用（排除 `.trae/documents/`、`docs/archive/`、`.ccc/archive/`）：

| 文件 | 行号 | 残留内容 | 处理方式 |
|------|------|----------|----------|
| `.ccc/infrastructure.md` | 64 | 注释 `# 对话面模型出口（默认已走 relay :4000；设此值强制直连）` | 改为 `:4100`（注释中的描述性文字） |
| `docs/ccc-hub-ports.md` | 23 | 端口表 `4000` 行描述「旧 CCC Relay M1（已退役）」 | 保持（历史记录，描述旧状态） |
| `docs/deploy/migration-m1-to-2017.md` | 15 | 迁移表中 `CCC Relay（:4000/:4002）` | 保持（历史参照表，描述迁移前状态） |
| `docs/deploy/migration-m1-to-2017.md` | 46 | 验证命令 `curl http://127.0.0.1:4000/admin/status` | 保持（历史步骤，已标注废弃） |
| `docs/relay/DEPLOY-2017.md` | 28, 36 | 历史参考中的旧端口和验证命令 | 保持（历史参考章节，已标注废弃） |
| `docs/relay/DEPLOY-2017.md` | 52 | 当前替代方案表中 `2017 验证 :4000` | 保持（描述旧操作，对应新操作已更新） |
| `docs/product/desktop-agent-handoff.md` | 101 | 提及 `:4000` 技术细节 | 此文件不在 24 文件列表中，但可考虑更新 |

### 非目标文件中的引用（仅供参考，不修改）

下有文件不在 24 文件列表中，但 grep 显示有 `:4000`/`:4002` 引用：

1. **`CHANGELOG.md`** — 历史记录，不改
2. **`references/adapters/runtime-opencode.md`** — 行 143-144 有 `:4002` 引用，需评估是否更新
3. **`tests/scripts/test_config_env.py`** — 测试期望值 `:4000`，需评估
4. **`tests/scripts/test_executor.py`** — 测试期望值 `:4000`，需评估
5. **`tests/scripts/test_ops_probe.py`** — 注释中有 `:4000`/`:4002`，需评估
6. **`tests/scripts/test_relay_fail_open_integration.py`** — 测试期望值 `:4000`，需评估
7. **`scripts/` 源文件** — 注释中的历史引用和字符串切片 `[:4000]`（非端口引用）

## 修改计划

### 变更 1: `.ccc/infrastructure.md` 行 64 注释更新

- **文件**: `.ccc/infrastructure.md`
- **位置**: 行 64，客户端环境变量示例中的注释
- **当前内容**: `# 对话面模型出口（默认已走 relay :4000；设此值强制直连）`
- **目标内容**: `# 对话面模型出口（默认已走 ai-loop-router :4100；设此值强制直连）`
- **原因**: 这是注释中的描述性文字，引用当前默认出口

### 变更 2: `docs/ccc-hub-ports.md` 行 23 端口表更新

- **文件**: `docs/ccc-hub-ports.md`
- **位置**: 行 23，端口表
- **当前内容**: `| **4000** | 旧 CCC Relay M1（已退役） | **M1** | 旧对话面模型路由（flash 档）；已迁移至 ai-loop-router :4100 |`
- **目标内容**: `| **4000** | 旧 CCC Relay M1（已退役） | **M1** | 旧对话面模型路由；已迁移至 ai-loop-router :4100 |`
- **原因**: 保留端口号 `4000` 作为历史记录（端口号本身是事实），但可简化为描述

### 变更 3: `docs/deploy/migration-m1-to-2017.md` 行 15 迁移表更新

- **文件**: `docs/deploy/migration-m1-to-2017.md`
- **位置**: 行 15，迁移表
- **当前内容**: `| CCC Relay（:4000/:4002） | M1 本机（旧 ai-loop-router） | **2017 生产实例** ...`
- **目标内容**: 保持当前内容，这是历史参照表，描述迁移前的状态
- **决策**: 不修改，保持历史准确性

### 变更 4: `docs/relay/DEPLOY-2017.md` 历史参考保留

- **文件**: `docs/relay/DEPLOY-2017.md`
- **决策**: 不修改，文档已标注废弃，旧端口在历史参考章节中保持历史准确性

### 变更 5（可选）: 非目标文件更新

- `references/adapters/runtime-opencode.md` 行 143-144：更新 `:4002` 为 `:4102`
- `tests/scripts/test_config_env.py` 行 86：更新期望值
- `tests/scripts/test_executor.py` 行 47, 52, 61, 66, 200：更新期望值
- `tests/scripts/test_relay_fail_open_integration.py` 行 90, 94：更新期望值

## 决策说明

1. **历史文档中的旧端口**：对于明确标注为「历史参照」「已废弃」的章节中的旧端口号，保持原样以确保历史准确性
2. **注释中的描述性引用**：如 `.ccc/infrastructure.md` 行 64 的注释，应更新为当前值
3. **端口号与端口描述的区别**：`4000` 作为端口号本身（如表格中的端口号列）可以保留，但描述文字中的引用应更新
4. **测试文件**：是否更新需与用户确认，因为测试期望值可能对应实际运行的配置

## 验证步骤

1. 修改完成后，运行 `grep -n ':4000\|:4002'` 在目标文件上确认无残留
2. 排除 `docs/archive/`、`.trae/documents/`、`.ccc/archive/`、`CHANGELOG.md` 等应保留历史记录的文件
3. 确认每个修改处的上下文正确（端口号 vs 字符串切片 `[:4000]`）