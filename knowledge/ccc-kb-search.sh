#!/usr/bin/env bash
# CCC 知识库检索脚本（T51 对齐统一查询内核）
# 后端 = server/kb/cli.py（与 kb MCP / 大脑同一 service 内核，BM25 + 去重 + 域过滤）
# 用法：
#   bash knowledge/ccc-kb-search.sh <关键词> [--domain <域>]       # 检索
#   bash knowledge/ccc-kb-search.sh <关键词> --domain <域> [--top-k N]
#   bash knowledge/ccc-kb-search.sh --list [--domain <域>]          # 列条目
#   bash knowledge/ccc-kb-search.sh --health                        # 健康自检
set -euo pipefail

KB_ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$KB_ROOT/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
    echo "用法: $0 <关键词> [--domain <域>] [--top-k N]"
    echo "       $0 --list [--domain <域>]"
    echo "       $0 --health"
    echo "域: nodes-paths | projects | decisions | lessons"
    exit 1
}

# 解析参数：仅识别 --domain/--top-k/--list/--health/-h，其余透传给 CLI
CMD="search"
KEYWORD=""
DOMAIN=""
TOP_K=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --top-k)
            TOP_K="$2"
            shift 2
            ;;
        --list)
            CMD="list"
            shift
            ;;
        --health)
            CMD="health"
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            if [[ -z "$KEYWORD" ]]; then
                KEYWORD="$1"
            else
                usage
            fi
            shift
            ;;
    esac
done

ARGS=( "$CMD" )
if [[ -n "$KEYWORD" ]]; then
    ARGS+=( "$KEYWORD" )
fi
if [[ -n "$DOMAIN" ]]; then
    ARGS+=( --domain "$DOMAIN" )
fi
if [[ -n "$TOP_K" ]]; then
    ARGS+=( --top-k "$TOP_K" )
fi

cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" -m server.kb.cli "${ARGS[@]}"
