# `executor-watchdog.sh` — Executor 启动前健康检查

> 启动 Executor (`claude -p ...`) 之前，检测系统状态，提前清理可能的 hang 进程 / stuck session，避免新任务被旧的卡死状态污染。

## 用途

Lesson 7 (2026-06-30 Mavis Executor 卡死) + Lesson 9 (fix-executor-hang task) 沉淀的防线。

## 用法

```bash
bash scripts/executor-watchdog.sh                  # 默认检查
bash scripts/executor-watchdog.sh --force-kill    # auto-clean
bash scripts/executor-watchdog.sh --quiet         # suppress output
```

## Exit codes

- **0** = 健康，可以启动 Executor
- **1** = 发现疑似 hang，已给提示但未清理（caller decide）
- **2** = 检测到严重问题，建议人工介入
- **3** = --force-kill 模式下清理了 hang 进程

## 检查项

1. **CPU/内存检查**：当前进程列表中是否有进程跑 ≥ 15 分钟 + CPU < 1%（claude 疑似卡）
2. **Mavis stuck session 检查**：`mavis session list` 看是否有 stuck
3. **端口冲突检查**：Executor 启动的端口（默认 8000）是否被占用
4. **OM 内存检查**：可用内存 < 1GB 时报警

## Example

```bash
# 标准用法 — 在 executor 启动前调用
bash scripts/executor-watchdog.sh || {
    echo "watchdog returned $?, decide: continue / --force-kill / 放弃"
    exit $?
}

# 用在 executor 启动 prompt 的开头
if ! bash scripts/executor-watchdog.sh --quiet; then
    bash scripts/executor-watchdog.sh --force-kill
fi

# 失败时 caller 决定
if ! bash scripts/executor-watchdog.sh; then
    case $? in
        1) echo "warning, continue" ;;
        2) echo "aborting" ; exit ;;
        3) echo "killed old hang, continue" ;;
    esac
fi
```

## 关联

- `references/red-lines.md` § 红线 9 (Executor 卡死止损)
- `docs/lessons.md` § Lesson 7, 9 (mavis 卡死教训)
