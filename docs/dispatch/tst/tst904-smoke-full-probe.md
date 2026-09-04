# 任务卡 tst904 · smoke: A1-A2 full-probe（DSH 执行）

> 关联：阶段 3 P1 · 执行体：DSH · 验收：DSH · 状态：打回（CC 审核不通过） · 派发：engine · 项目：tst · 日期：2026-09-03 · 状态版本：6

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
2. 引擎收单后主仓卡：`## 回写区

## 0. 卡标题复述

tst904 · smoke: A1-A2 full-probe（DSH 执行）

## 1. 探针输出

按任务卡「步骤」节执行 3 条只读命令，以下为原始输出与退出码：

```text
$ git -C /Users/fan/program/CCC rev-parse --short HEAD
805a32e6e
(exit=0)

$ curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:7788/health
000
(exit=7)

$ ls /Users/fan/program/apps/ccc-tst/math_utils.py
/Users/fan/program/apps/ccc-tst/math_utils.py
(exit=0)
```

## 2. 自测输出

卡内未声明独立测试、编译或 lint 门禁；本卡为只读探针卡，红线明确禁止业务仓写操作及 commit/push。无额外自测命令；自测结果等同上述 3 条只读探针：主仓 HEAD 退出码 `0`；health 退出码 `7`、输出 `000`；业务文件探针退出码 `0`。

## 0. 卡标题复述

（完整复述卡标题）

`tst904 · smoke: A1-A2 full-probe（DSH 执行）`

## 1. 探针输出

按任务卡「步骤」节执行 3 条只读命令，以下为原始输出与退出码：

#

## 2. 自测输出

卡内未声明独立测试、编译或 lint 门禁；本卡为只读探针卡，红线明确禁止业务仓写操作及 commit/push。因此无额外自测命令；自测结果等同上述 3 条只读探针：主仓 HEAD 退出码 `0`；health 退出码 `7`、输出 `000`；业务文件探针退出码 `0`。

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

1. 方案同步：[否][无] 说明：本卡仅执行只读链路探针，未要求同步方案。
2. 教训沉淀：[否][无] 说明：本卡仅回传探针结果；health 探针不可达属于本次环境实测现象，不在本卡范围内形成沉淀。
3. 档案/README：[否][无] 说明：卡红线禁止业务仓写操作，未修改项目结构、技术栈或路径。
4. 线路图：[否][无] 说明：本卡不改变项目近况或下一步，仅回传 A1/A2 链路探针结果。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：完成钩子：维护区只找到 0/4 问
