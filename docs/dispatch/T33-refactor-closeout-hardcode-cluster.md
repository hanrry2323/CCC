# 任务卡 T33 · 重构收口：硬编码清零 + 集群/运维服务清单修正（D10 收口）（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§9 全局红线 / D10 杜绝硬编码）
> 依据：Codex 2026-08-03 全新取证重评——engine/cluster.py `DEFAULT_SERVICES` 硬编码且服务名仍是旧系统（ccc-chat-server/ccc-board-server，2017 已下线），集群/运维页会误报；legacy-chat 前端仍硬编码本机路径与 IP（utils.js/ports.js/settings.js）
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03

## 目标

全仓服务端/前端硬编码清零（D10 永久纪律收口），集群/运维页按新栈真实服务（web-server/engine/board-scheduler）正确展示。

## 红线（先看）

1. 只改 server/ 与 server/web/ 内的配置/采集/前端读取逻辑；不动 2017 运行面、不改 board API 协议（T30 已定）。
2. 前端保持纯 html/css/js，不引第三方框架；配置注入端点不得泄露密钥。
3. 服务名/进程关键词以 2017 部署现状为准（与 T22 部署记录核对），不确定就标「待核」不瞎填。
4. 真实提交；验收标准不可自行解释。

## 范围

server/engine/cluster.py、server/config/（loader.py、config.example.env）、server/web/server.py（如需只读配置注入端点）、server/web/legacy-chat/js/（utils.js、ports.js、settings.js 及受影响文件）、server/tests/、server/engine/README.md。

## 步骤

1. cluster.py：`DEFAULT_SERVICES` 移除，服务清单改 config.env 键驱动（如 `CLUSTER_SERVICES=name:process_keyword` 逗号分隔）；默认示例值改为新栈：web-server / engine / board-scheduler（进程关键词与 2017 launchd 实际一致，先核对 `ssh 192.168.3.116 "launchctl list | grep ccc"` 或 T22 部署记录，拿不到就标待核）。
2. config.example.env 补 `CLUSTER_SERVICES` 占位与注释；loader 支持列表键解析。
3. 前端：utils.js 绝对路径、ports.js 硬编码 IP、settings.js workspace map 默认值 → 改为服务端只读注入（如 `/config` 端点返回 base_url/workspace 映射，免鉴权白名单仅返回非敏感字段）或相对地址；全页面统一读取，删除散落字面量。
4. 补单测：cluster 服务清单解析（含空/坏格式）、配置注入端点字段与鉴权（非敏感字段才免鉴权）。
5. 三扫描自检（硬编码/密钥/外脑引用）后提交。

## 验收标准

1. 三扫描零命中（含前端 js）；`rg -n "DEFAULT_SERVICES|192\.168\.3\.116:7777|/Users/apple" server/ --glob '!**/__pycache__/**'` 零命中（测试夹具除外）。
2. M1 本地起服务实测：`/ops/summary` 返回的服务名/进程清单为新栈三服务；`/config`（如新增）不泄露密钥。
3. 页面实测登录后看板/运维/对话仍全 200（T30 功能不回退）。
4. `pytest server/tests -q` 全绿；真实提交。

## 回写要求

卡头状态更新为「已回写」；回写区填：清单改动、2017 服务核对结果（或「待核」项）、前端注入方案、测试输出、commit hash。

## 回写区

**执行体**：Trae · 日期：

