# 任务卡 tst904 · smoke: A1-A2 full-probe（DSH 执行）

> 关联：阶段 3 P1 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：tst · 日期：2026-09-03 · 状态版本：1

## 基准文件（先看）

- 项目基准：`docs/projects/tst/README.md`（方案池与项目说明）。
- 业务仓 `/Users/fan/program/apps/ccc-tst/`（Mac2017）为只读参考；本卡不读取也不改动它之外的任何内容。
- 方案池：`docs/projects/tst/plans/`（关联方案见卡头「关联」）。

## 目标

管线全链路冒烟（只读探针）· 验证 A1/A2 新链路：执行体只在 worktree 干活并写 `.ccc-result.md`，引擎代写主仓卡回写区/维护区四问/卡头已回写。

## 实现要求

执行体必须先通读本卡全文，仅执行「步骤」节命令，把输出如实写入 worktree 根的 `.ccc-result.md`。禁止修改主仓卡文件、禁止直接填卡回写区/改卡头状态（引擎代做）。

## 红线（先看）

1. 只读探针卡：禁止任何写操作（不碰业务仓文件、不改配置、不 commit/push 业务仓）。
2. 禁止修改主仓卡文件（只读指针）；卡回写由引擎代做。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

docs/dispatch/tst/tst904-smoke-full-probe.md

## 步骤

1. 执行下列 3 条只读命令，把原始输出写入 worktree 根 `.ccc-result.md`：
   - `git -C /Users/fan/program/CCC rev-parse --short HEAD`
   - `curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:7788/health`
   - `ls /Users/fan/program/apps/ccc-tst/math_utils.py`
2. `.ccc-result.md` 必须含四段：`## 0. 卡标题复述`（完整复述本卡标题）、`## 1. 探针输出`、`## 2. 自测输出`、`## 3. 维护区四问`（逐项[是/否][有/无]+说明）、`## 4. 变更证据`。
3. 写完后停手，等引擎代写主仓卡。

## 验收标准

1. worktree 根存在 `.ccc-result.md`，含卡标题复述「tst904 · smoke: A1-A2 full-probe」与 3 条命令原始输出。
2. 引擎收单后主仓卡：`## 回写区\n\n## 0. 卡标题复述

任务卡标题（完整复述）：`tst904 · smoke: A1-A2 full-probe（DSH 执行）`
关联工作项：tst904 · 阶段 3 P1 · 执行体：DSH · 验收：DSH · 项目：tst · 日期：2026-09-03
卡片性质：管线全链路冒烟（只读探针），验证 A1/A2 新链路；执行体仅在 worktree 干活并写 `.ccc-result.md`，引擎代写主仓卡回写区/维护区四问/卡头已回写。

## 1. 探针输出

按卡「步骤」节 3 条只读命令执行，原始输出如下（含退出码）：

| # | 命令 | 输出 | 退出码 | 说明 |
|---|------|------|--------|------|
| 1 | `git -C /Users/fan/program/CCC rev-parse --short HEAD` | `2e0d63fdf` | 0 | CCC 主仓 HEAD 可解析，短哈希 2e0d63fdf |
| 2 | `curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:7788/health` | `000` | 7 | 退出码 7 = Failed to connect to host；本地 127.0.0.1:7788 未监听从服务，health 端点不可达（疑似本会话未拉起该服务） |
| 3 | `ls /Users/fan/program/apps/ccc-tst/math_utils.py` | `/Users/fan/program/apps/ccc-tst/math_utils.py` | 0 | 文件存在 |

原始输出明细（stdout/stderr）：
```
$ git -C /Users/fan/program/CCC rev-parse --short HEAD
2e0d63fdf   (exit=0)

$ curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:7788/health
000   (exit=7, 连接失败/本地未监听)

$ ls /Users/fan/program/apps/ccc-tst/math_utils.py
/Users/fan/program/apps/ccc-tst/math_utils.py   (exit=0)
```

## 2. 自测输出

卡「门禁」节未声明测试/编译/lint 命令（scope=false），且本卡为只读探针卡（红线 1：禁止任何写操作、不 commit/push 业务仓）。因此本卡无门禁自测需执行；自测步骤等同于上方 3 条只读探针命令的如实执行结果，已全部记录于「\n

## 维护区

1. **方案同步**：[否]（本卡为冒烟探针，无关联方案）
   - 说明：卡头「关联」为阶段 3 P1，未声明具体方案；步骤节未要求同步任何方案，故无方案同步动作。
2. **教训沉淀**：[无]
   - 说明：本卡为只读链路冒烟，未产出可复用代码/文档/流程教训；探针 2 显示本地 127.0.0.1:7788 未监听属环境侧现象，非本卡范围内沉淀对象。
3. **档案/README**：[否]
   - 说明：本卡红线 1 明令禁止任何写操作；未修改任何项目结构/技术栈/路径，业务仓 `/Users/fan/program/apps/ccc-tst/` 全程只读。
4. **线路图**：[否]
   - 说明：本卡不改变项目近况/下一步；仅完成 A1/A2 新链路冒烟探针并回传原始输出，引擎据此回写主仓卡即可。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：回写契约不完整且结果工件缺失
