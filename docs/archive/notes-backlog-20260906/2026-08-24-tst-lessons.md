# tst 教训 · 2026-08-24 · 门禁假绿：分支 worktree 缺 gitignored 配置致泄漏类测试基线绿

- 来源卡：tst004（管线修复验证·合入竞态防护与部署测试封闭化）。
- 现象：server/tests/test_server.py 两用例（test_build_ports_payload_empty / test_chat_bridge_token_empty）在主检出 /Users/fan/program/CCC 必挂（server/config/config.env 含 CLUSTER_PORT_NAMES=…,6100:relay-anthropic,… 与 CCC_CHAT_BRIDGE_TOKEN），但在新开的分支 worktree（如 /Users/fan/program/CCC-wt/tst004）基线却绿——config.env 是 gitignored 文件，只存在于主检出，worktree 里根本没有。
- 根因：被测函数经 `_env_or_config` 先 env 后 config.env 回落；「泄漏源」是否在场取决于哪个检出跑门禁，门禁绿 ≠ 生产绿。
- 教训：封闭化不能依赖环境巧合，必须隔离配置读取源本身（patch `_env_or_config` 返回空串），并优先在生产检出（config.env 在场处）复现红基线后再验证修复转绿；凡测试涉及 env→config 回落读取，一律按「双源都可能污染」处理。

## 教训二 · 门禁命令按首个 ASCII 冒号切键值会在 pytest node-id `::` 处腰斩 → 机审假阳性 exit 127

- 来源卡：tst004 同卡第 1/2 轮机审误打回。
- 现象：门禁行 `测试：cd …; python3 -m pytest server/tests/test_server.py::TestPortNetwork::… -q` 被证据采集器按第一个 ASCII 冒号切成键值对，取值段变成 `:TestPortNetwork::…`，执行得 `command not found`，exit_code=127；机审机械门禁据此判「测试真实失败」打回，而被测代码从未真实跑过。
- 根因：键值分隔应认声明分隔符全角「：」，而非行内任意首个 ASCII 冒号；pytest node-id 的 `::` 是合法路径字符。解析器与调用方（test-evidence.sh / engine parse_gate_section）同源口径时缺陷会成对出现。
- 教训：①凡「key：value」类文档解析优先按全角冒号/行首键名切分，ASCII 冒号可能是数据；②机审证据链要区分「命令没跑起来」与「断言失败」——127/命令不存在类退出码先核采集器，再定罪被测代码；③执行体遇疑似假阳性应留存原始证据日志与最小复现（Python 逐字节复现解析），供平台侧定位，不越权改白名单外文件。平台侧已热修：主仓 main `e21e974d2`（test-evidence 优先全角冒号）。
