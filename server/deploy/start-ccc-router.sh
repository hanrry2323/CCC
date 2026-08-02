#!/bin/bash
# CCC 独立中转站启动脚本 — 端口 6100/6102（Mac2017 独立实例）
# 与 M1 4100/4102 并存、互不冲突
# 用法: ./scripts/start-ccc-router.sh [start|stop|status|restart]

PROJECT_DIR="/Users/fan/program/apps/ai-loop-router-ccc"
NODE_BIN="/usr/local/bin/node"
ENTRY_FILE="$PROJECT_DIR/dist/proxy.js"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/.ccc-router.pid"

export LOOP_ANTHROPIC_PORT=6100
export LOOP_OPENAI_PORT=6102

mkdir -p "$LOG_DIR"

start() {
    if [ -f "$PID_FILE" ]; then
        OLDPID=$(cat "$PID_FILE")
        if kill -0 "$OLDPID" 2>/dev/null; then
            echo "CCC 中转站已在运行 (PID: $OLDPID)"
            return 0
        else
            echo "清理过期 PID 文件"
            rm -f "$PID_FILE"
        fi
    fi

    echo "启动 CCC 独立中转站 (6100/6102)..."
    cd "$PROJECT_DIR"
    nohup "$NODE_BIN" "$ENTRY_FILE" \
        > "$LOG_DIR/stdout.log" 2> "$LOG_DIR/stderr.log" &
    PID=$!
    echo $PID > "$PID_FILE"
    sleep 2

    if kill -0 "$PID" 2>/dev/null; then
        echo "✅ 启动成功 (PID: $PID)"
        echo "   日志: $LOG_DIR/stdout.log + stderr.log"
        echo "   端口: 6100 (anthropic) / 6102 (openai-chat)"
        echo "   Dashboard: http://127.0.0.1:6100/dashboard"
        return 0
    else
        echo "❌ 启动失败，查看日志:"
        tail -30 "$LOG_DIR/stderr.log"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "未发现 PID 文件，无运行实例可停止"
        return 0
    fi
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "停止 CCC 中转站 (PID: $PID)..."
        kill "$PID"
        for i in {1..10}; do
            kill -0 "$PID" 2>/dev/null || break
            sleep 0.5
        done
        if kill -0 "$PID" 2>/dev/null; then
            echo "强制 kill..."
            kill -9 "$PID"
        fi
        echo "✅ 已停止"
    else
        echo "进程不存在，清理过期 PID"
    fi
    rm -f "$PID_FILE"
}

status() {
    echo "--- CCC 独立中转站状态 ---"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "✅ 运行中 (PID: $PID)"
            lsof -i :6100 -i :6102 -P 2>/dev/null | grep LISTEN || echo "   (端口监听检测中...)"
            return 0
        else
            echo "⚠️  PID 文件存在但进程已不存在"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo "❌ 未运行"
        return 1
    fi
}

case "${1:-start}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    *) echo "用法: $0 [start|stop|restart|status]"; exit 1 ;;
esac