#!/usr/bin/env bash
# M1 开发实例启动（8899 端口）——知识库基建 P4 后标准启动方式。
# 必需：CLUSTER_HP_TARGET（/ops/kb-health 探活）+ HP_KB_URL（hp_client 混合检索/健康度）。
# 用法：bash server/deploy/start-m1-dev.sh   （后台挂起：nohup ... &）
cd "$(dirname "$0")/../.." || exit 1
export CLUSTER_HP_TARGET="${CLUSTER_HP_TARGET:-192.168.3.131:8083}"
export HP_KB_URL="${HP_KB_URL:-http://192.168.3.131:8083/mcp}"
exec /opt/homebrew/bin/python3 -m server.web.server --port 8899 --host 127.0.0.1
