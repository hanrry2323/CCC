# deploy/ — 进程编排

> T1 已完成 · 只产模板与脚本，不注册 launchd、不启动服务（红线：不碰运行面）。

## 内容

| 文件 | 职责 |
|------|------|
| `com.ccc.engine.plist` | 进程编排模板：占位变量 `$PROJECT_ROOT` / `$ENGINE_ENTRY` / `$CONFIG_ENV` / `$LOG_DIR` / `$DATA_DIR` / `$USERNAME`，部署前替换 |
| `run.example.sh` | 启动模板：`--config` 指定 `config.env`；必填 `ENGINE_PORT` / `PYTHON_BIN`；以 `$PYTHON_BIN -m server.engine.main --config …` 启动 |
| `health.example.sh` | 健康检查模板：探活 Engine `/health`，输出 JSON（engine_up / engine_latency_ms / log_dir_writable） |

## 关键约定

- **零字面量**：解释器走 `$PYTHON_BIN`；无绝对路径、无字面端口、无字面工具名。
- 占位变量风格：`$UPPER_SNAKE`；部署前替换为真实值，**禁止把真实值写回模板**。
- 硬编码扫描（验收通过线）：黑名单 `/Users`、字面端口 `:[4-9][0-9]{3}`、模型名、工具名；对 `server/` 内 `.py/.sh/.plist/.env` 零命中（`tests/` 夹具与 `config/executors.example.json` 配置除外）。

## 与相邻模块关系

| 模块 | 关系 |
|------|------|
| `engine/` | run 启动 `server.engine.main`；health 探活其 `/health` |
| `config/` | 脚本 source `config.env`；loader 二次校验必填项 |
| `tests/` | 冒烟测试覆盖模板存在性与语法（bash -n / plist lint） |

## 施工入口

- T2 后：`run.example.sh` 的 `server.engine.main` 即真实入口。
- T4 后：落地真实部署（运行面，需管理席许可，单独执行）。
- `com.ccc.tunnel-watchdog.plist` + `../scripts/ops/tunnel-watchdog.sh`：每 300 秒探测本机隧道，M1 可达时按需 kickstart 恢复并追加日志。
