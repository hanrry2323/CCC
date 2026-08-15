#!/usr/bin/env bash
# HP 知识库部署脚本（2026-08-16 流程改造 P5 交付承接）
# 参照 mx deploy.sh 模式，目标 hp@192.168.3.131:/data/knowledge（知识权威在 HP 节点）。
# ⚠️ 状态：可执行参照——待 HP 子项目（源码回灌 SSOT）交付时固化到 hp 业务仓 scripts/ 并实测重启命令。
# 用法: scripts/deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="$(cat "${ROOT}/VERSION" 2>/dev/null || echo dev)"
NODE="hp@192.168.3.131"
DEPLOY_DIR="/data/knowledge"

echo "=== HP 知识库 v${VER} 部署 ==="

echo "→ 确保目标目录..."
ssh "${NODE}" "mkdir -p ${DEPLOY_DIR}/mcp-server ${DEPLOY_DIR}/memory-store ${DEPLOY_DIR}/pipeline ${DEPLOY_DIR}/scripts ${DEPLOY_DIR}/backups"

echo "→ 同步代码（mcp-server / memory-store / pipeline / scripts）..."
rsync -arz --delete --exclude __pycache__ "${ROOT}/mcp-server/" "${NODE}:${DEPLOY_DIR}/mcp-server/"
rsync -arz --delete --exclude __pycache__ "${ROOT}/memory-store/" "${NODE}:${DEPLOY_DIR}/memory-store/"
rsync -arz --delete --exclude __pycache__ "${ROOT}/pipeline/" "${NODE}:${DEPLOY_DIR}/pipeline/"
rsync -arz --exclude __pycache__ "${ROOT}/scripts/" "${NODE}:${DEPLOY_DIR}/scripts/"

echo "→ 备份（回滚保险，保留最近 5 份）..."
ssh "${NODE}" "TS=\$(date -u +%Y%m%dT%H%M%SZ); tar czf ${DEPLOY_DIR}/backups/hp-code.\${TS}.tar.gz ${DEPLOY_DIR}/mcp-server ${DEPLOY_DIR}/memory-store ${DEPLOY_DIR}/pipeline 2>/dev/null; ls -t ${DEPLOY_DIR}/backups/hp-code.*.tar.gz | tail -n +6 | xargs -r rm -f; echo \"  backup: hp-code.\${TS}.tar.gz\""

echo "→ 重启服务（PG 不重启；MCP/memory-store 重启方式以 hp 仓部署手册为准）..."
echo "  ⚠️ 待 hp 节点实测固化：MCP 经 ~/.claude/settings.json 注册、memory-store 为常驻进程，"
echo "     典型重启：ssh hp 'pkill -f memory_store; nohup ... &' 或 systemd（如配置）。"

echo "→ 健康检查（探活 8083 MCP / 8082 memory / 5432 PG）..."
ssh "${NODE}" "ss -lnt | grep -E ':(8082|8083|5432)\b' | awk '{print \$4}' | sort -u || echo '(未探通，待实测)'"

echo "=== HP 部署完成 ==="
echo "  代码: ${NODE}:${DEPLOY_DIR} · 版本: v${VER}"
