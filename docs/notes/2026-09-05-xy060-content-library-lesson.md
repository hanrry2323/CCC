# xy060 内容库 API 可复用教训

日期：2026-09-05

## 1. 业务 worktree 测试环境复用业务仓 `.venv` symlink

业务仓型 worktree 不应复制或新建虚拟环境；业务仓根已有 `.venv` 时，由 Engine 将其以 `worktree/.venv -> business_repo/.venv` 符号链接挂载，测试与 lint 直接复用同一环境。没有 `.venv` 时保持不阻断并明确告警。这样可避免执行体在隔离 worktree 中因缺少依赖而产生环境性失败，同时不把环境文件写入业务仓提交。

证据：`server/engine/main.py`、`server/tests/test_engine_main.py`；CCC commit `6718d9c27fe5c4419d79ab6d8e4a0944eafe8da7`（feat(engine): mount business worktree venv symlink）；验证记录 `docs/notes/2026-09-05-xianyu-worktree-venv-report.md`。

## 2. DSH/后段验收输出须编码容错，维护区格式须匹配门禁解析器

DSH/后段验收链路读取和转发中文输出时应保持无损或具备编码容错，避免 verdict/结果文本因解码问题丢失；维护区四问的选择与说明应使用门禁解析器能够识别的格式，并在教训声明中引用本记录或其他实际 `docs/notes/*.md` 文件。否则真实实现可能因工件解析失败或维护区证据缺失而被门禁拒绝，不能用过程日志替代独立证据。

证据：`server/engine/phase2.py`、`server/tests/test_phase2.py`、`scripts/cc-auditor.sh`、`server/board/docgate.py`；CCC commits `dabf6ef2b0ae49645b6c51a0ea4e5f6a74326278`（fix(phase2): decode auditor output losslessly）与 `780ef676b`（fix(docgate): accept inline maintenance choices）；验证记录 `docs/notes/2026-09-05-phase2-decode-fix-report.md`、`docs/notes/2026-09-05-dsh-tool-bash-fix-report.md`。
