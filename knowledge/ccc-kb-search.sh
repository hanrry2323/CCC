#!/usr/bin/env bash
# CCC 知识库基础检索脚本
# 用法：
#   bash knowledge/ccc-kb-search.sh <关键词>              # 全文检索
#   bash knowledge/ccc-kb-search.sh <关键词> --domain <域> # 指定域检索
#   bash knowledge/ccc-kb-search.sh --list --domain <域>   # 列出域内所有条目
set -euo pipefail

KB_ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
    echo "用法: $0 <关键词> [--domain <域>]"
    echo "       $0 --list --domain <域>"
    echo "域: nodes-paths | projects | decisions | lessons"
    exit 1
}

# 解析参数
KEYWORD=""
DOMAIN=""
LIST_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --list)
            LIST_MODE=true
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

# 确定搜索范围
if [[ -n "$DOMAIN" ]]; then
    DOMAIN_DIR="$KB_ROOT/domains/$DOMAIN"
    if [[ ! -d "$DOMAIN_DIR" ]]; then
        echo "错误: 未知域 '$DOMAIN'"
        echo "可用域:"
        for d in "$KB_ROOT/domains"/*/; do
            echo "  - $(basename "$d")"
        done
        exit 1
    fi
    SEARCH_PATH="$DOMAIN_DIR"
else
    SEARCH_PATH="$KB_ROOT/domains"
fi

if $LIST_MODE; then
    # 列出域内所有条目标题
    find "$SEARCH_PATH" -name '*.md' -exec grep -n '^### ' {} /dev/null \; | \
        sed 's|.*/domains/\([^/]*\)/.*:### \(.*\)|  [\1] \2|'
    exit 0
fi

if [[ -z "$KEYWORD" ]]; then
    usage
fi

# 执行检索
echo "=== 检索关键词: '$KEYWORD' ==="
echo ""

RESULTS=$(grep -rn -i "$KEYWORD" "$SEARCH_PATH" --include='*.md' -l 2>/dev/null || true)

if [[ -z "$RESULTS" ]]; then
    echo "无匹配结果"
    exit 0
fi

echo "匹配文件:"
echo "$RESULTS" | while read -r f; do
    DOMAIN_NAME=$(echo "$f" | sed 's|.*/domains/\([^/]*\)/.*|\1|')
    echo "  [$DOMAIN_NAME] $f"
done

echo ""
echo "--- 匹配行 ---"
grep -rn -i --color=always "$KEYWORD" "$SEARCH_PATH" --include='*.md' | \
    sed 's|.*/domains/\([^/]*\)/\([^:]*\):\([^:]*\):\(.*\)|  [\1] \2:\3 → \4|'