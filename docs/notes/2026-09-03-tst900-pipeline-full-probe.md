# 测试卡全流程实测 · 阻塞诊断（2026-09-03）

> 卡：tst900-smoke-full-flow · 目标：验证「出卡→执行→机审→回写」主链可用性
> 方法：分步只读核查 + 落卡 + 执行通道探针，暴露问题不打包票

## 一、分类器阻塞根因核查（指令一）

| 项 | 值 | 命令证据 |
|---|---|---|
| 当前模型通道 | `ANTHROPIC_BASE_URL=http://127.0.0.1:3456` · model `Code` | `env | grep -i anthropic` |
| 3456 是什么 | 本地 SSH 隧道到 M1 中转站（scnet-free 档，`~/.zshrc:37-39`） | `lsof -iTCP:3456` → `ssh 33035 LISTEN` |
| 3456 是否活着 | 是，多连接 ESTABLISHED | `lsof` 显示 claude.exe 与 3456 双向活跃 |
| 最小写动作测试 | `touch /tmp/claude-write-test` → `WRITE OK` | 分类器写动作已恢复 |

**结论**：分类器超时不是通道死（3456 活、代理在、连接在），更像 CLI 模型通道瞬时抖动（与 09-02「直连已退役、429×3」同源怀疑）。一次最小写已恢复，暂不切通道。

## 二、卡落盘 + 看板索引（指令二.1）

- 落卡：`scripts/new-card.sh --project tst --id tst900-smoke-full-flow` → `[OK] 出卡成功 + validate 通过`
  - 尾部 git 报错（`.git/index.lock`）与卡本身无关，卡文件 5800 字节已落盘
- 带 token 读看板：`/cards?project=tst&q=tst900` → **返回 tst900，state=待分派，executor=DSH** ✅ 看板索引识别
- 结论：出卡→看板索引 环节通。

## 三、执行通道（指令二.2）—— 当前阻塞

engine 日志（`~/.ccc/logs/engine.stderr.log`）：
```
heartbeat: {"mode":"loop", "scanned":0, "dispatched":0, ...}
phase2 前置检查失败: 工作区脏（未提交改动 74 项）→ 本轮跳过消费，卡保留已回写待下轮
```

**两条根因**：
1. **工作区脏 74 项**（即本轮早先清理的 74 个计划文件，因分类器超时未能 commit）→ engine phase2 完全跳过消费。
2. `scanned:0` → 主循环这轮没扫到任何待分派卡，engine `pending = store.list_work(state=State.TODO)` 返回空。
   - engine 扫描目录 = `DISPATCH_DIR=docs/dispatch`（`config.env` 确认）。
   - board API 能查到 tst900，但 engine store 未同步到 → store 缓存问题（待 engine 重启或下次心跳后应刷新）。

**要跑通执行，必须先 commit 那 74 个计划文件**（解除 engine 脏区阻断）。

## 四、看板登录密码（顺带小修一）

已重置前台账号 `ccc`/密码 `ccc`：
- `web-auth.txt` 格式：服务端读 `口令:<明文>` 自行 SHA-256 比对，**不是存哈希**（初次误判成哈希写入导致 401，更正为明文后 200）。
- `POST /session` → 200，token 64 位；带 token `/cards`、`/board/ready_for_merge` 均 200。

## 五、看板同步挂 2 天（顺带小修二，未动手）

上次已确认：`board-live.sh` 于 08-30 `5795c6f` 被迁走 + 读闸 08-29 起要 Bearer token。修复需两处：重挂 launchd 调度 + 脚本加 token 鉴权。本轮未动手，因先要解除脏区阻断。
