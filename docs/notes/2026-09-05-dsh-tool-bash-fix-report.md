# DSH tool-bash 修复报告（2026-09-05）

## 结论

已修复当前 DSH 实际加载的 `@deepseek-ai/dsh-tool-bash` 本体：当 bash executor 的 `sandboxMode` 为 `danger-full-access` 时，不再向模型注册 `sandbox_permissions` / `justification` 字段，也不再附带同回合升级指导。受限模式仍保留原升级契约；sandbox resolver 的严格拓宽逻辑未修改。

## 修改与回滚

- 实际加载路径：`/Users/fan/.dsh/profiles/node_modules/@deepseek-ai/dsh-tool-bash`（符号链接指向全局 DSH 安装）
- 修改文件：`/Users/fan/.npm-global/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-tool-bash/lib/index.js`
- 变更：`apply()` 中将 escalation mode 判定改为：无 sandbox executor 或 `danger-full-access` → `[]`；其余有 sandbox 的模式继续使用 `ESCALATION_TARGETS`。
- 备份：同目录 `lib/index.js.bak-20260905-toolbash-fix`
- 回滚：将该备份覆盖回 `lib/index.js`；未修改 xianyu 业务仓、CCC engine/web，也未重启服务。

## 独立验证证据

1. 语法：
   - `node --check .../dsh-tool-bash/lib/index.js`
   - 结果：退出码 0，无输出。
2. schema/description 脚本验证（直接 import 当前修改后的模块并构造 executor）：
   - `danger-full-access`：参数为 `command, description, timeoutMs, workdir, run_in_background`；不含 `sandbox_permissions`、`justification`；description 不含升级指导。
   - `workspace-write`：参数保留 `sandbox_permissions`、`justification`；description 保留升级指导。
   - 无 sandbox mode：不含两字段、不含升级指导。
3. 安全回归：独立检查 `dsh-sandbox/lib/index.js` 仍保留严格判断：只有 `WIDER_MODES[effectiveMode]` 包含 requested mode 才通过；`danger-full-access → danger-full-access` 仍抛出 `not strictly wider`。
4. 真实 headless 冒烟：在隔离临时 cwd 执行 `dsh --profile headless "echo 1"`，退出码 0，输出为 `1`；未出现 `not strictly wider`。
5. CCC 仓状态：`git status --short --branch` 在报告写入前显示 `main...origin/main`，本次仅新增本报告；DSH 用户级 node_modules 修改不属于 CCC git 工作树。

## 证据边界

schema 脚本验证的是当前实际加载的 tool-bash 模块注册结果；headless 冒烟验证真实 CLI 正常执行。未重启 CCC engine/web，亦未将 xy060 手工 kill 或重派。
