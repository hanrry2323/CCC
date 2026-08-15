#!/usr/bin/env bash
# scripts/sync-kb-index.sh
# 检测 knowledge/ 目录变更并自动重建 KB 索引
set -euo pipefail

# 默认配置，支持环境变量覆盖
KB_DIR="${KB_DIR:-knowledge}"
MARKER_FILE="${MARKER_FILE:-$KB_DIR/.index/.last_sync_marker}"
LOG_FILE="${LOG_FILE:-$KB_DIR/.index/sync.log}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# 解析参数
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "未知参数: $1" >&2
            echo "用法: $0 [--dry-run]" >&2
            exit 1
            ;;
    esac
done

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    if [[ "$DRY_RUN" = false ]]; then
        mkdir -p "$(dirname "$LOG_FILE")"
        echo "$msg" >> "$LOG_FILE"
    fi
}

# 检查 Python 环境
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    echo "错误: 未找到 Python 解释器 ($PYTHON_BIN)" >&2
    exit 1
fi

# 检查是否需要同步
NEED_SYNC=false
CHANGES=""

if [[ ! -f "${MARKER_FILE}" ]]; then
    NEED_SYNC=true
    CHANGES="首次运行（未找到标记文件 ${MARKER_FILE}）"
else
    # 查找是否有更新的文件（排除 .index 和标记文件本身）。
    # 不用 `find | head -1`：批量新增条目时 find 输出多行，head 提前关闭管道触发 SIGPIPE(141)，
    # 令脚本在重建索引前即被终止。改由命令替换一次性收齐 find 输出、再用 bash 参数展开取首行，
    # find 全程无管道读方提前关闭，杜绝 SIGPIPE。
    CHANGED_ALL=$(find "${KB_DIR}" -path "*/.index" -prune -o -path "*/.*" -prune -o -newer "${MARKER_FILE}" -print)
    CHANGED_FILE="${CHANGED_ALL%%$'\n'*}"  # 取首个变更文件（换行分片取首段）
    if [[ -n "${CHANGED_FILE}" ]]; then
        NEED_SYNC=true
        CHANGES="检测到文件变更: ${CHANGED_FILE}"
    fi
fi

if [[ "${NEED_SYNC}" = true ]]; then
    if [[ "${DRY_RUN}" = true ]]; then
        log "Dry run: 需要重建索引。原因: ${CHANGES}"
    else
        log "开始重建索引。原因: ${CHANGES}"
        if "${PYTHON_BIN}" -m server.kb.mcp_server --reindex; then
            log "索引重建成功。"
            # 更新标记文件
            mkdir -p "$(dirname "${MARKER_FILE}")"
            touch "${MARKER_FILE}"
        else
            log "错误: 索引重建失败！"
            exit 1
        fi
    fi
else
    log "未检测到变更，跳过索引重建。"
fi
