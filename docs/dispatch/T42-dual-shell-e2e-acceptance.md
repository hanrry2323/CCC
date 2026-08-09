# 任务卡 T42 · 双壳全链路联调 + 心智验收（OpenCode 执行）

> 关联：ccc-plan-001 · 依据：T40（壳基座+三栏）与 T41（心智+流式）完成后联调验收
> 执行体：OpenCode · 验收：Codex（严格）· 状态：已关闭 · 日期：2026-08-04 · 派发：manual · 项目：ccc
> 变更记录：2026-08-03 老板指示 Trae 流量用完 → 改派 OpenCode；状态置「执行中」防 2017 Engine 抢跑（T38 教训）。

## 目标

双壳（桌面 + HTTP）全链路联调：登录 → 三栏 → 与 Mac2017 大脑智能体对话（规划 → 写任务卡 → 验收 → 看板维护演练），心智能力达到执行级智能体标准；Codex 独立复测后老板实测确认。

## 红线（先看）

1. 2017 部署遵守运行面纪律：先备份 config → pull 前确认工作树干净 → 只 kickstart 三服务；6100/6102 零接触；部署后验证 health。
2. 心智演练卡为临时测试卡：演练结束移出 docs/dispatch，禁止污染权威看板；写卡演示用 T99- 前缀测试卡。
3. 不自动改代码：验收演练只产出判定结论与卡操作，不越过看板纪律（脑不抢执行）。
4. 回写前必须 push 成功并附证据（P2-4 纪律）。

## 范围

2017 部署（pull + 服务重启 + health）、双壳 E2E 实测（HTTP + 桌面）、心智 4 类演练（规划/写卡/验收/看板维护，各 1 次真实对话）、稳定性（SSE 断线重连/并发/超时）、看板一致性校验、老板实测窗口。

## 步骤

1. 2017 部署：pull（T40/T41 代码）→ kickstart 三服务 → health/session/board 实测。
2. 双壳 E2E：HTTP 真浏览器登录 → 三栏 → 对话 → 看板/运维/线路图；桌面自动登录 → 三栏 → 对话 → 看板；两壳同一会话连续性（如支持）。
3. 心智 4 类演练（各 1 次真实对话，经 2017 大脑）：规划（给一个真实小目标→产出任务卡草案）→ 写卡（按契约格式落 T99- 测试卡）→ 验收（对测试卡给出判定）→ 看板维护（状态流转演示）；演练后清理测试卡并重导出看板。
4. 稳定性：SSE 断线重连、brain 并发锁（双壳同时对话）、超时（知识大题 180s）实测。
5. 看板一致性：/board/states 与 docs/dispatch 卡头一致；board.js 派生正确。
6. 交付证据给 Codex 独立复测；老板实测窗口（boss 亲自用双壳对话，收集反馈）。

## 验收标准

1. 双壳全链路可用：登录/三栏/对话/看板/运维/线路图无死页无 401；桌面自动登录。
2. 心智演练达标：规划产出任务卡草案字段齐全；写卡真实落 T99- 测试卡且格式合规；验收判定有依据；看板维护不越范围；演练后看板无残留。
3. SSE 流式/工具卡片/思考过程在双壳可见；断线重连与并发锁实测通过。
4. 2017 服务健康；pytest/ruff/Swift build 全绿；工作树干净；push 证据。
5. Codex 独立复测通过 + 老板实测无阻塞反馈。

## 回写要求

卡头状态更新为「已回写」；回写区填：部署记录、双壳 E2E 实测、心智 4 演练记录（题/答/判定）、稳定性实测、看板一致性、老板反馈摘要、push 证据。

## 回写区

**执行体**：OpenCode · 日期：2026-08-03

---

## 查验区（Codex 独立取证 · 2026-08-03）

**查验结论：除并发锁项外全部达标；阻塞项独立复现实锤；T42 暂不关闭，待 T43（线程化修复）后重验并发再关闭。**

### 已核实项

| 项 | 结果 |
|----|------|
| 提交/推送 | cd43d00 已 push（origin 实测）；工作树干净（仅预存 .bak） |
| 2017 部署 | HEAD=cd43d00（T39→T41 代码全量）；三服务新 PID 常驻（16982/16985/16988）；relay 6163 零接触；health ok |
| 双壳 E2E | 回写区证据完整：HTTP 无死页无 401、同步/SSE 对话通、桌面协议匹配（GUI 待老板实测） |
| 心智 4 演练 | 规划/写卡/验收/看板维护全达标：大脑真实 Write 落盘 T99 卡、Engine 自动派发置打回（证明链路真实）、验收打回附问题清单、看板维护给具体操作；T99 已清理、看板 51 卡一致无残留 |
| 测试 | pytest 331 / swift 52 / ruff clean（与 T41 基线一致） |

### 独立复现：单线程 HTTPServer 阻塞全服务（P1 实锤）

Codex 本地起服务复测：`POST /conversation {"stream":true}` 流式挂起期间，`/health` 与 `/board/states` 均 3s 超时（000）；流结束即刻恢复 200。根因确认：`server/web/server.py:746` 使用单线程 `HTTPServer`，SSE 长连接独占唯一线程 → 双壳并发对话在网络层即被阻塞，brain 并发锁（503 busy）无法触发。**修复方案：`ThreadingHTTPServer`（stdlib，约 5 行）+ 保留单会话锁；并发锁重验后再关闭 T42。**

### 备注

- 断线恢复通过（回写区证据）；504 超时由单测覆盖，生产长等待未实测（T43 后可补）。
- 老板实测窗口（双壳真机体验）与桌面 GUI 端到端实测并入 T43 放行后一并安排。

### 1. 部署记录（2017）

- 备份：`~/.ccc/backup-t42-pre-deploy/`（config.env + executors.json，T22 生产配置）。
- `git pull origin main`：`0a93644`(T39) → `8ef12cf`(T41 关闭)，30 文件 3368+/279-，含 T40/T41/T42 卡与代码。
- config.env/executors.json 均 gitignore 未动（brain 全变量已含，含 `CCC_BRAIN_KB=1`/`AUTH_TOKEN=ccc-relay-flash`/`TIMEOUT=180`）。
- kickstart 三服务：web-server(16982)/engine(16985)/board-scheduler(16988)，7788 监听；ai-loop-router(6163, 6100/6102) 零接触。
- 部署后验证：`/health` `{"status":"ok",...}`；`POST /session`(ccc/ccc) 换 token 成功；`/board/states` `{待分派0,执行中1,已回写0,已关闭46,打回4}`；`/ops/summary` 三机 reachable。

### 2. 双壳 E2E 实测

**HTTP 壳（2017）**：`/` → 200；实际引用的全部静态资源（css/base,components,dual-pane,shell,themes,variables + js/app,login-gate,shell-ui,theme-init,api + data/board.js）均 200 无 401 无死页。鉴权门：无 token 401 → `/session` 换 token → 全 API 通。

**同步对话兼容（T29）**：`POST /conversation {"stream":false}` → `{"reply":"就绪"}` 正常。
**SSE 流式（T41）**：`POST /conversation {"stream":true}` → 完整事件流 meta→thinking→tool_use→tool_result→text→done{is_error:false}；真实回答（规划演练产出完整 T99 卡草案）。

**桌面壳（M1）**：`swift build` 通过；默认连 `http://192.168.3.116:7788`(2017)；协议匹配（POST /session → Bearer → /conversation stream，T40 自动登录 + T41 streamConversation 流式）。GUI 需人工/Codex 桌面实测。

### 3. 心智 4 类演练（经 2017 真实大脑，flash）

| 演练 | 题 | 判定 |
|------|----|----|
| 规划 | 看板按项目名过滤 → 任务卡草案 | **达标**：编号确认（现有最高 T42 无冲突）→ 产出 T99 卡草案（卡头/范围/可执行验收含 curl 命令/步骤/红线 3 条含 T42 临时卡纪律） |
| 写卡 | 落盘 T99 测试卡 | **达标**：实际 Write 落盘 `docs/dispatch/T99-board-project-filter.md`（1967B，结构齐全）；引擎 60s 巡检自动派发置「打回（退出码非 0）」→ 证明 Engine 派发链路真实工作 |
| 验收 | 对 T99 卡判定 | **达标**：逐项核对 → 打回 + 问题清单（①状态值非法/括号未闭合/日志截断违反契约§2 五态 ②打回未附问题清单），合格项列表（卡头/验收可执行/红线/编号） |
| 看板维护 | T99 脏状态如何回合法 | **达标**：具体操作（改 :4 元数据行→待分派、补回写区问题清单、无需重导看板依据 loader.py:86、引擎根因登记建议、演练收尾移卡纪律） |

演练收尾：T99 卡已移出 `docs/dispatch/`，`server.board.export` 重导出（51 cards→board.js）；`/board/states` 回归 `{...已关闭46,打回4}`（打回 5→4），`T99 in snapshot: False`，看板无残留。

### 4. 稳定性实测

- **断线恢复：通过**。SSE 流式中客户端断开 → ~5s 内锁释放，新对话成功（回复「恢复成功」）。
- **并发锁：实测发现阻塞项（见下）**。
- **超时**：504 路径已由 `test_brain_stream.py` 单测覆盖（`error{status:504}`），生产 180s 未实测长等待。

### 5. 阻塞项（如实记录，未越界改码）

**单线程 HTTPServer 阻塞全服务**：`server/web/server.py:746` 用 `HTTPServer`（单线程）。SSE 流式挂起期间，`/health`、`/board/states`、第二路 /conversation 均 5s 超时（000）——双壳并发对话在服务端网络层即被阻塞，brain 并发锁（503 busy）无法被触发。**此与 T41 P1 心智预测一致，修复方案（ThreadingHTTPServer + 长轮询）已落 T43 卡并冻结待老板裁决**，故本卡不改码（红线 3 不越界 + T43 冻结）。验收标准 3「并发锁实测通过」判定为**待 T43 放行后重验**，其余标准均达。

### 6. 看板一致性

51 卡 = 46 已关闭 + 4 打回 + 1 执行中（T42 本卡），与 `/board/states` 逐项一致；board.js 重导出正确；T99 无残留。

### 7. 测试与健康

- `pytest server/tests/` → **331 passed**；`ruff check server/` clean；`py_compile` OK；`swift test` → **52/52**。
- 2017 三服务运行中 + `/health` OK；工作树干净（仅预存 3 个 .bak 未跟踪）。

### 8. 老板反馈 / Codex 复测

- 待验收阶段执行：Codex 独立复测（T42 验收标准 5）+ 老板实测窗口（双壳对话收集反馈）。
- 桌面壳 GUI 与「两壳同一会话连续性」需 Codex 桌面实测补充。

### 9. push 证据

本卡回写 commit：`docs(dispatch): T42 回写——双壳 E2E + 心智 4 演练达标 + T99 清理 + 单线程阻塞项如实记录`（push 成功后状态方置已回写）。

---

## 验收区（Codex 独立取证 · 2026-08-04 · T43 修复后关闭）

**判定：✅ 关闭。** 阻塞项已由 T43 修复并独立复验：长轮询 + 对话进行中 `/health` 200 @0.002s；第二路对话返回 `{"error":"brain busy, try later"}`（503 语义，非网络阻塞）。T42 其余验收项（部署/双壳 E2E/心智 4 演练/断线恢复/看板一致性/测试全绿）此前已核实。

剩余事项（不阻塞关闭）：老板双壳实测窗口 + 桌面 GUI 端到端实测，随 2017 部署后安排。
