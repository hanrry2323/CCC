# ccc-fix-osascript-inject 执行报告

## 信息
- Phase: ccc-fix-osascript-inject-p1
- 退出码: 0

## 输出
```
{
  "phase_id": "ccc-fix-osascript-inject-p1",
  "exit_code": 0,
  "stdout": "Done. `scripts/ccc-notify.sh:55-62` 已改为 `osascript` 的 `on run` handler 传参机制，shell 变量不再嵌入 AppleScript 代码路径，阻止了注入向量。已以 `ccc-fix-osascript-inject` 开头 commit。\n",
  "stderr": "\u001b[0m\n> build · flash\n\u001b[0m\n\u001b[0m→ \u001b[0mRead scripts/ccc-notify.sh\n\u001b[0m\n\u001b[0m← \u001b[0mEdit scripts/ccc-notify.sh\nIndex: /Users/apple/program/CCC/scripts/ccc-notify.sh\n===================================================================\n--- /Users/apple/program/CCC/scripts/ccc-notify.sh\n+++ /Users/apple/program/CCC/scripts/ccc-notify.sh\n@@ -52,13 +52,13 @@\n   L1)\n     echo \"[ccc-notify] L1 (log only) $TITLE: $MESSAGE\"\n     ;;\n   L2)\n-    osascript -e \"display notification \\\"$MESSAGE\\\" with title \\\"CCC L2: $TITLE\\\"\" >/dev/null 2>&1\n+    osascript -e 'on run {m, t}' -e 'display notification m with title t' -e 'end run' -- \"$MESSAGE\" \"CCC L2: $TITLE\" >/dev/null 2>&1\n     echo \"[ccc-notify] L2 sent: $TITLE\"\n     ;;\n   L3)\n-    osascript -e \"display notification \\\"$MESSAGE\\\" with title \\\"CCC L3: $TITLE\\\" subtitle \\\"需要老板拍板\\\" sound name \\\"Basso\\\"\" >/dev/null 2>&1\n+    osascript -e 'on run {m, t}' -e 'display notification m with title t subtitle \"需要老板拍板\" sound name \"Basso\"' -e 'end run' -- \"$MESSAGE\" \"CCC L3: $TITLE\" >/dev/null 2>&1\n     echo \"[ccc-notify] L3 sent: $TITLE\"\n     ;;\n esac\n \n\n\u001b[0m\n\u001b[0m→ \u001b[0mRead scripts/ccc-notify.sh\n\u001b[0m\n\u001b[0m$ \u001b[0mbash -n scripts/ccc-notify.sh && echo \"SYNTAX OK\"\nSYNTAX OK\n\u001b[0m\n\u001b[0m$ \u001b[0mgit diff --stat\n.ccc/board/index.json | 4 ++--\n .ccc/metrics.json     | 4 ++--\n CHANGELOG.md          | 8 ++++++++\n scripts/ccc-notify.sh | 4 ++--\n 4 files changed, 14 insertions(+), 6 deletions(-)\n\u001b[0m\n\u001b[0m$ \u001b[0mgit diff scripts/ccc-notify.sh\ndiff --git a/scripts/ccc-notify.sh b/scripts/ccc-notify.sh\nindex e571155..5b67d5c 100755\n--- a/scri
```
