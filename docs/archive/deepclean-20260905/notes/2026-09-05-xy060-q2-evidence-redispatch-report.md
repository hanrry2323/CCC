# xy060 带鉴权重派与脚本支持证据

日期：2026-09-05

## 目标与边界

按 `~/.ccc/instructions/2026-09-05-xy060-redispatch-with-token.md` 执行：通过 `POST /session` 获取短期 Bearer token，再将 `xy060` 从「打回」正规转为「待分派」，并让 `scripts/redispatch-card.sh` 支持调用方通过 `CCC_BOARD_TOKEN` 注入 token。未修改卡正文、未手工启动 DSH、未修改 xianyu 业务代码、未发布。

## 鉴权配置核实

- 配置来源：`server/config/config.env` 的 `CCC_WEB_USERNAME` / `CCC_WEB_PASSWORD_HASH` / `CCC_WEB_TOKEN_TTL` / `CCC_WEB_WRITE_AUTH`；运行时也支持环境变量覆盖。
- 回退凭证文件：`/Users/fan/.ccc/web-auth.txt`；本次仅按文件格式读取账号和口令，未将口令、hash 或 token 输出、写入卡、脚本或本报告。
- 服务端实现：`server/web/server.py` 的 `_auth_credentials()` 从环境变量优先解析，回退支持「账号:」/「口令:」格式；`_handle_session()` 校验后签发内存短期 token；`_check_auth()` 对变更请求校验 `Authorization: Bearer`。

## 脚本变更

`scripts/redispatch-card.sh`（实际路径：`scripts/redispatch-card.sh`）：

- 新增 `CCC_BOARD_TOKEN` 环境变量读取。
- 非空时向 transition 请求加入 `Authorization: Bearer ${CCC_BOARD_TOKEN}`。
- token 只存在调用进程环境与请求头中，不写入脚本、卡文件或日志。
- 请求 body 仍为 `{"status":"待分派"}`，未改变卡正文。

## 实际执行证据

1. 通过 `POST /session` 使用现有凭证换取短期 token；响应 token 未输出。
2. 以 `CCC_BOARD_TOKEN` 调用 `bash scripts/redispatch-card.sh xy060`，返回：

   ```text
   [OK] xy060: {"ok": true, "id": "xy060", "from": "打回", "to": "待分派", "card": "/Users/fan/program/CCC/docs/dispatch/xy/xy060-content-library-api.md", "runtime": true}
   ```

3. 随后使用新 token 查询看板，返回 `xy060` 状态为 `执行中`、`board_column=执行中`、`executor=DSH`，证明 Engine 已自动认领并启动重派流程；未手工启动 DSH。
4. 独立运行 `bash -n scripts/redispatch-card.sh` 与 `git diff --check`，均通过。
5. `git diff -- docs/dispatch/xy/xy060-content-library-api.md` 无输出，卡正文无本次改动。

## 运行状态边界

本记录证明鉴权换 token、transition 成功以及 Engine 自动认领；不把执行过程自报当作业务交付验收证据。当前未执行合入或部署，也未声称业务卡已通过后段机审。
