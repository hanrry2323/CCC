# CCC 自动化流程运行手册

> 版本：v1.0 · 适用：CCC 自动化流程全链路 · 维护：2017 执行体

## 1. 流程链路

自动化流程共 7 步，串起 Codex、Engine、2017 执行体：

1. **Codex 出卡**：Codex 在 `docs/dispatch/` 新建任务卡（如 T99-flow-real），卡内写明工作目录、分支、任务内容、红线、验收标准。
2. **push**：Codex 推送任务卡分支到远程仓库（origin/main）。
3. **2017 pull**：2017 运行副本拉取最新 main，本地出现新任务卡。
4. **Engine 扫描派发**：Engine 扫描 `docs/dispatch/`，识别新卡 → 创建分支 → 自动派发给 2017 执行体。
5. **2017 执行体开发**：执行体在指定工作目录（ccc-dev-ws）开发，完成真实代码/文档改动，提交到分支。
6. **push 分支**：执行体推送开发分支（如 `codex/flow-real-001`）。
7. **Codex 验收 → 合入 main**：Codex 按卡内验收标准检查分支，通过后合入 main；2017 运行副本 pull + 服务重启（部署），任务闭环。

## 2. 状态流转

任务卡状态沿固定路径流转：

- **待分派** → **执行中** → **已回写** → **已关闭**

规则：

- 执行体开始工作即置为「执行中」。
- 分支推送、回写结果写入卡头回写区后置为「已回写」。
- Codex 验收通过合入后置为「已关闭」。
- **失败打回**：验收不通过时打回，附问题清单，退回「待分派」重新处理，直至通过。

## 3. 关键命令

Engine 手动触发（单次扫描派发）：

```bash
$PYTHON_BIN -m server.engine.main --config server/config/config.env --once
```

看板导出（任务卡状态刷新到前端看板）：

```bash
$PYTHON_BIN -m server.board.export --dispatch-dir docs/dispatch --output server/web/data/board.js
```

服务重启（部署，三服务）：

```bash
launchctl kickstart -k gui/$(id -u)/<engine 服务>
launchctl kickstart -k gui/$(id -u)/<board 服务>
launchctl kickstart -k gui/$(id -u)/<web 服务>
```

> `$PYTHON_BIN` 为运行环境对应的 Python 解释器路径，按部署环境替换。

## 4. 测试任务先行纪律

**正式任务前必须跑 T9x-test 占位卡**，验证流程跑通后再投正式任务：

1. 先投 T9x-test 占位卡，走完整链路（出卡 → 派发 → 执行 → 回写 → 验收）。
2. 流程跑通后，正式任务卡才允许投入。
3. 测试卡验收通过后**删除，不留残留**（卡文件与分支清理干净）。

## 5. 常见问题

- **本地卡文件改动导致 pull 失败**：执行体可能本地改过任务卡文件，与远程冲突。处理：先 `git checkout -- docs/dispatch/<卡文件>` 丢弃测试卡改动，再 pull。
- **执行体工作目录**：执行体只在 `ccc-dev-ws` 开发；**禁止修改 2017 运行副本（/Users/fan/program/CCC）任何文件**，运行副本仅做 pull + 部署。
