# OBS3: 流程压力探针

**Task ID:** cla-obs3-docs  
**创建时间:** 2026-07-17  
**探针类型:** 流程压力探针（non-functional, non-feature, non-bug）

## 目的

本探针作为全链路压力测试凭证，独立于具体功能开发或改进，旨在验证 CCC Loop Pipeline 的端到端完整性：
- backlog → product → dev → commit 全流程可无障碍走通
- 看板状态转换机制正常
- 文档/配置/代码交付路径清晰
- Git 仓库状态管理规范

通过此类探针的定期运行（OBS1/2/3），可横向校验系统整体健康度，而不依赖业务功能本身。

## 验收

本探针的验收标准依赖于 OCC 文档规范与 Git 约定，而非代码执行结果：

### 触发条件

1. **Doc 存在性**: `docs/OBS3.md` 已被 Git 索引
2. **Commit 标识**: 最新 commit message 包含 `cla-obs3-docs`
3. **范围控制**: Git diff 范围仅包含白名单文件列表指定的文件
4. **报告完整性**: `.ccc/reports/cla-obs3-docs.report.md` 已写入且包含 HEAD commit hash

### 验收标准

| 检查点 | 执行命令 | 预期结果 |
|--------|----------|----------|
| OBS3 存在 | `git ls-files docs/OBS3.md` | 返回文件路径（非空） |
| Commit 含标识 | `git log -1 --oneline \| grep cla-obs3-docs` | 零退出码 |
| 范围控制 | `git diff --name-only HEAD\~1..HEAD` | 仅含 `docs/OBS3.md` 与 `.ccc/reports/cla-obs3-docs.report.md` |
| 报告含 HEAD | `head -3 .ccc/reports/cla-obs3-docs.report.md` | 文件首行出现 commit hash |

## 交付物

- `docs/OBS3.md` — 流程压力探针文档（本文件）
- `.ccc/reports/cla-obs3-docs.report.md` — 执行报告（含 git log 验证）

## 扩展说明

- 本探针不引入新逻辑，仅充当“临床试验”凭证
- 运行成功后，可在后续轮次中继续交付 OBS1/OBS2 同类探针，作为横切面检查
- 若后续 pipeline 发生变更（如 phase 流水线结构调整），应同步更新本探针的验收清单
