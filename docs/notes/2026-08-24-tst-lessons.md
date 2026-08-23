# tst 教训 · 2026-08-24 · 门禁假绿：分支 worktree 缺 gitignored 配置致泄漏类测试基线绿

- 来源卡：tst004（管线修复验证·合入竞态防护与部署测试封闭化）。
- 现象：server/tests/test_server.py 两用例（test_build_ports_payload_empty / test_chat_bridge_token_empty）在主检出 /Users/fan/program/CCC 必挂（server/config/config.env 含 CLUSTER_PORT_NAMES=…,6100:relay-anthropic,… 与 CCC_CHAT_BRIDGE_TOKEN），但在新开的分支 worktree（如 /Users/fan/program/CCC-wt/tst004）基线却绿——config.env 是 gitignored 文件，只存在于主检出，worktree 里根本没有。
- 根因：被测函数经 `_env_or_config` 先 env 后 config.env 回落；「泄漏源」是否在场取决于哪个检出跑门禁，门禁绿 ≠ 生产绿。
- 教训：封闭化不能依赖环境巧合，必须隔离配置读取源本身（patch `_env_or_config` 返回空串），并优先在生产检出（config.env 在场处）复现红基线后再验证修复转绿；凡测试涉及 env→config 回落读取，一律按「双源都可能污染」处理。
