# fix-hardcoded-home-path 执行报告

## 信息
- Phase: fix-hardcoded-home-path-p1
- 退出码: 0

## 输出
```
{
  "phase_id": "fix-hardcoded-home-path-p1",
  "exit_code": 0,
  "stdout": "Done. `scripts/ccc-engine.sh:18` 的 `/Users/apple/.npm-global/bin` → `$HOME/.npm-global/bin`。60 tests passed, commit `79f9be1`。\n",
  "stderr": "\u001b[0m\n> build · code\n\u001b[0m\n\u001b[0m# \u001b[0mTodos\n[•] Read scripts/ccc-engine.sh to see the hardcoded path\n[ ] Replace /Users/apple/ with $HOME in ccc-engine.sh\n[ ] Run pytest to verify 59+ passed\n[ ] Commit with message fix-hardcoded-home-path\n\u001b[0m\n\u001b[0m→ \u001b[0mRead scripts/ccc-engine.sh\n\u001b[0m\n\u001b[0m← \u001b[0mEdit scripts/ccc-engine.sh\nIndex: /Users/apple/program/CCC/scripts/ccc-engine.sh\n===================================================================\n--- /Users/apple/program/CCC/scripts/ccc-engine.sh\n+++ /Users/apple/program/CCC/scripts/ccc-engine.sh\n@@ -14,8 +14,8 @@\n WS_SLUG=$(basename \"${CCC_WORKSPACE}\")\n LOG=\"${LOG_DIR}/engine-${WS_SLUG}-${$}.log\"\n \n # 修复 launchd 环境缺 PATH\n-export PATH=\"/Users/apple/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin\"\n+export PATH=\"$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin\"\n export OPENCODE_MODEL=\"${OPENCODE_MODEL:-loop/code}\"\n \n exec python3 \"$CCC_HOME/scripts/ccc-engine.py\" --workspace \"$CCC_WORKSPACE\" >> \"$LOG\" 2>&1\n\n\u001b[0m\n\u001b[0m# \u001b[0mTodos\n[✓] Read scripts/ccc-engine.sh to see the hardcoded path\n[✓] Replace /Users/apple/ with $HOME in ccc-engine.sh\n[•] Run pytest to verify 59+ passed\n[ ] Commit with message fix-hardcoded-home-path\n\u001b[0m\n\u001b[0m$ \u001b[0mpython3 -m pytest tests/scripts/ -v --tb=short 2>&1 | tail -30\ntests/scripts/test_ccc_init_search_smoke.py::test_init_creates_profile_md PASSED [ 55%]\ntests/scripts/test_ccc_init_search_smoke.py::test_init_skips_existing_ccc PASSED [ 56%]\ntests/scripts/test_ccc_init_search_smoke.py::test_search_syntax PASSED   [ 58%]\ntests/scripts/test_ccc_init_search_smoke.py::test_search_finds_pattern PASSED [ 60%]\ntests/scripts
```
