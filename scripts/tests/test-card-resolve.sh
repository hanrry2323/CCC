#!/usr/bin/env bash
# V7 测试：resolve_card 唯一性断言（多命中报错，禁止 head -1 猜）。
set -uo pipefail

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/docs/dispatch/ccc"
touch "$TMP/docs/dispatch/ccc/ccc777-alpha.md"

cd "$TMP"
source /Users/apple/program/CCC/scripts/lib/card-resolve.sh

R1="$(resolve_card ccc777)"
[[ "$R1" == "docs/dispatch/ccc/ccc777-alpha.md" ]] || { echo "FAIL: 唯一命中未返回正确路径 ($R1)"; exit 1; }

R2="$(resolve_card ccc999 2>&1)" && { echo "FAIL: 不存在的卡未报错"; exit 1; }
[[ "$R2" == *"找不到卡"* ]] || { echo "FAIL: 找不到卡错误信息缺失 ($R2)"; exit 1; }

touch "$TMP/docs/dispatch/ccc/ccc777-beta.md"
R3="$(resolve_card ccc777 2>&1)" && { echo "FAIL: 二义性未报错"; exit 1; }
[[ "$R3" == *"二义性"* && "$R3" == *"ccc777-alpha"* && "$R3" == *"ccc777-beta"* ]] || { echo "FAIL: 二义性错误信息不完整"; exit 1; }

echo "V7 resolve_card 测试全过"
