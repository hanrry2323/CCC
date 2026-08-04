# zcode-adapter-v121 Review

## Verdict: **PASS**

## Size Class: **large** (439 行)

通过。脚本结构清晰，遵循 CCC 红线和惯例，9/9 smoke 测试覆盖完整。5 个 low 发现 + 1 个 medium（JSON heredoc 注入风险）多属防御性编码规范，不影响当前功能。bash -n 语法通过。新文件不修改现有管线代码，风险低。

## Findings (6 条)

```json
{
  "verdict": "pass",
  "findings": [
    {
      "severity": "medium",
      "file": "scripts/ccc-zcode-bridge.sh",
      "line": 140,
      "issue": "spawn 报告通过 shell heredoc 创建，$WORKSPACE 变量直接在 JSON 内展开。若 WORKSPACE 包含双引号或反斜杠（用户输入场景），JSON 语法会损坏。脚本其他位置都用 python3 json 模块安全写入。",
      "suggestion": "第 140-152 行的 heredoc JSON 改为 python3 写入（与行 210-219、241-252 统一）。python3 -c 内用小写变量名做 json.dumps 可避免注入。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-zcode-bridge.sh",
      "line": 222,
      "issue": "set +e 在脚本以 set -uo pipefail（无 -e）启动后是无操作的。set -e 在第 236 行才启用，不对称模式误导读者以为之前需要禁用 -e。",
      "suggestion": "移除第 222 行的 set +e 和第 236 行的 set -e。CLAUDE_EXIT=$? 即使 set -e 生效也会正确捕获退出码（Bash 语义）。"
    },
    {
      "severity": "low",
      "file": ".ccc/phases/zcode-adapter-v121.phases.json",
      "line": 1,
      "issue": "Phase 1 状态为 'done' 但 commit 为 null。按约定完成的 phase 应引用提交哈希（eaccb5a）。phases.json 末尾缺少换行符（JSONL 格式违规）。",
      "suggestion": "commit 字段设为 eaccb5a，文件末尾加换行。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-zcode-bridge.sh",
      "line": 184,
      "issue": "$WATCHDOG 脚本存在性在调用前未检查。若 executor-watchdog.sh 被删除或重命名，报错为 Bash 默认 'No such file or directory'，排查不直观。",
      "suggestion": "在运行 watchdog 前添加 [[ -f \"$WATCHDOG\" ]] 检查，显式报错并写进 spawn 报告。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-zcode-bridge.sh",
      "line": 169,
      "issue": "wc -l < file | tr -d ' ' 中 tr 是多余的——wc 输入重定向时只输出数字，无前导空格。",
      "suggestion": "简化为 PROMPT_LINES=$(wc -l < \"$PROMPT_FILE\")"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-zcode-bridge.sh",
      "line": 66,
      "issue": "凭证提取用 grep -oE 匹配 JSON 键值对，仅支持单行格式。合法的多行 JSON 凭证文件会静默失败，ANTHROPIC_AUTH_TOKEN 留空，Claude 调用在运行时失败。",
      "suggestion": "保持当前简化方式（避免 jq 依赖），但在 token 为空时加显式警告并存证到 spawn 报告，便于事后排查。"
    }
  ],
  "summary": "通过。脚本结构清晰，遵循 CCC 红线和惯例，9/9 smoke 测试覆盖完整。5 个 low 发现 + 1 个 medium（JSON heredoc 注入风险）多属防御性编码规范，不影响当前功能。bash -n 语法通过。新文件不修改现有管线代码，风险低。"
}
```
