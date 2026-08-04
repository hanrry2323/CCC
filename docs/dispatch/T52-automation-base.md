# 任务卡 T52 · 自动化基建：出卡模板 + 一键放行 + 验收自动化（Claude Code 执行）

> 关联：阶段 3 P1 · 依据：规划确认——Codex 只留「验收+放行」；出卡/门禁/部署自动化
> 执行体：Claude Code · 验收：Codex（严格）· 状态：已关闭 · 日期：2026-08-04
> 作废记录：2026-08-04 方向调整——同 T51，作废待 2017 执行环境跑通后重出。
> 并行执行：**工作目录 `/Users/apple/program/ccc-ws-p1b`（分支 `codex/p1b-auto-base`）**，与 T51 并行；文件所有权见下

## 目标

自动化基建三件套：出卡模板脚本、一键放行部署脚本、验收自动化（卡头门禁 CI + headless 复验脚本），并用一条测试流程任务端到端验证。

## 具体项

1. **出卡模板** `scripts/new-card.sh`：生成标准卡骨架（项目前缀+三位序号+slug 命名、卡头字段、目标/红线/范围/步骤/验收标准/回写要求/回写区）；自动查重（validate 联动）+ 编号自增。
2. **一键放行** `deploy/release.sh <commit|tag>`：2017 pull → 三服务 kickstart → 自动验证（/health、/session 或免登录直连、/board/states、/projects、一次对话）→ 输出放行报告；卡头状态自动更新「已关闭」（验收席放行后）。
3. **验收自动化**：
   - validate.py 接入 CI（.github/workflows/ci.yml）+ pre-commit（新卡格式门禁：字段/状态/编号唯一）；
   - `scripts/verify-shell.sh`：headless 复验固化（免登录直进/流式/思考折叠无空占位/切界面不断流/左栏业务项目/零 console error）一键跑。
4. **测试流程任务先行（老板硬性要求）**：用 release.sh 跑一条 `T9x-test` 占位卡端到端（出卡→执行→验收→放行→看板可见→**删除测试卡无残留**），跑通后才允许正式任务走该链路。

## 红线

- 只改 scripts/、deploy/、.github/workflows/ci.yml、.pre-commit-config.yaml、server/board/validate.py、docs/（流程说明）；**禁止改 server/kb/、knowledge/、brain.py（T51 所有权）**。
- release.sh 不碰生产配置（config.env 只读检查）；测试卡用占位改动，跑完删除。
- 回写前必须 push 成功并附证据。

## 验收标准

1. `new-card.sh` 生成合规卡（validate 通过 + 编号唯一）。
2. `release.sh` 在 M1 模拟 + 2017 实测通过（含自动验证段）；测试流程任务端到端跑通且**删除后看板无残留**。
3. validate 门禁在 CI/pre-commit 生效（故意放一张坏卡被拦的演示记录）。
4. `verify-shell.sh` 全场景 PASS；pytest 全绿、ruff/py_compile clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：三件套实现说明、测试流程任务跑通记录（含看板可见/删除无残留）、CI 门禁演示、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code · 日期：
