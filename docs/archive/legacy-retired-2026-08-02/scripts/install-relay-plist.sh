#!/bin/bash
# install-relay-plist.sh — 已退役（2026-08-01 relay 清理）
# 
# CCC relay/ 目录已删除，统一使用 M1 的 ai-loop-router（/Users/apple/program/ai-loop-router）。
# 请参考 docs/deploy/topology.md 了解当前拓扑。
#
# 用法：
#   在 M1 上手动启动 ai-loop-router：
#     cd /Users/apple/program/ai-loop-router && npm run dev
#   （或通过 launchd 管理：com.ai-loop-router.plist）
#
# 历史：
#   该脚本曾用于安装 CCC relay/ 的 launchd plist，在 M1 和 Mac2017 各跑独立实例。
#   2026-08-01 后统一由 M1 的 ai-loop-router 提供中转服务。

set -uo pipefail

echo "❌ install-relay-plist.sh 已退役（2026-08-01 relay 清理）"
echo ""
echo "CCC relay/ 已删除，统一使用 M1 的 ai-loop-router（端口 4100/4102）。"
echo ""
echo "在 M1 上启动："
echo "  cd /Users/apple/program/ai-loop-router && npm run dev"
echo ""
echo "Mac2017 通过 http://192.168.3.140:4100/:4102 使用 M1 的中转站。"
echo ""
echo "详细拓扑见：docs/deploy/topology.md"
exit 0