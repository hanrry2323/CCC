#!/usr/bin/env bash
# 一键打开 CCC Desktop（强制连 Mac2017 Hub）
export CCC_SERVER="${CCC_SERVER:-http://192.168.3.116:7777}"
defaults write com.ccc.desktop "ccc.server" -string "$CCC_SERVER"
defaults write com.ccc.desktop "ccc.user" -string "${CCC_CHAT_USER:-ccc}"
defaults write com.ccc.desktop "ccc.pass" -string "${CCC_CHAT_PASS:-ccc}"
pkill -x CCCDesktop 2>/dev/null || true
sleep 0.3
open -a CCCDesktop
echo "已打开 CCC Desktop → $CCC_SERVER"
