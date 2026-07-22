#!/usr/bin/env bash
# install-ops-plist.sh — 安装 Ops Scheduler（日 diff / 文档审）launchd 模板
# 用户显式启用；不是 invent。默认 --no-enable 写入 disabled-ccc，避免偷偷跑。
# --apply-ammo: ProgramArguments 加 --all-apps --apply（仅 C/E/F + medium docs；禁 orch）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CCC_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
ACTION="${1:-install}"
ENABLE_NOW=false
APPLY_AMMO=false
HOUR=7
MINUTE=30

usage() {
  cat <<EOF
Usage: $(basename "$0") [install|uninstall|status] [--enable] [--apply-ammo] [--hour H] [--minute M]

安装两个 LaunchAgent（默认写到 ~/Library/LaunchAgents/disabled-ccc/）:
  com.ccc.ops-daily-diff   → ccc-daily-diff-review.py --all-apps
  com.ccc.ops-docs-review  → ccc-daily-docs-review.py --all-apps

加 --enable 才会 launchctl load（且要求控制面非 disabled 时更安全）。
加 --apply-ammo 才会在 plist 写入 --apply（C/E/F 与 docs medium+ 可建卡；D/G/H/I 不建开发卡）。
默认 dry-run（只写报告）。

Examples:
  $(basename "$0") install
  $(basename "$0") install --enable --apply-ammo --hour 8 --minute 0
  $(basename "$0") uninstall
  $(basename "$0") status
EOF
}

shift_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --enable) ENABLE_NOW=true; shift ;;
      --apply-ammo) APPLY_AMMO=true; shift ;;
      --hour) HOUR="$2"; shift 2 ;;
      --minute) MINUTE="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) shift ;;
    esac
  done
}

# re-parse after ACTION
shift_args "${@:2}"

if ${ENABLE_NOW}; then
  PLIST_DIR="${HOME}/Library/LaunchAgents"
else
  PLIST_DIR="${HOME}/Library/LaunchAgents/disabled-ccc"
fi
mkdir -p "${PLIST_DIR}" "${CCC_HOME}/.ccc/logs"

write_plist() {
  local label="$1"
  local script="$2"
  local plist="${PLIST_DIR}/${label}.plist"
  local apply_xml=""
  if ${APPLY_AMMO}; then
    apply_xml="    <string>--apply</string>"
  fi
  cat > "${plist}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>${CCC_HOME}/scripts/${script}</string>
    <string>--all-apps</string>
${apply_xml}
  </array>
  <key>WorkingDirectory</key><string>${CCC_HOME}/scripts</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>${CCC_HOME}/scripts</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>${HOUR}</integer>
    <key>Minute</key><integer>${MINUTE}</integer>
  </dict>
  <key>StandardOutPath</key><string>${CCC_HOME}/.ccc/logs/${label}.out.log</string>
  <key>StandardErrorPath</key><string>${CCC_HOME}/.ccc/logs/${label}.err.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
PLIST
  echo "wrote ${plist} (apply_ammo=${APPLY_AMMO})"
  if ${ENABLE_NOW}; then
    launchctl unload "${plist}" 2>/dev/null || true
    launchctl load "${plist}"
    echo "loaded ${label}"
  else
    echo "not loaded (use --enable). Plist in disabled-ccc or LaunchAgents."
  fi
}

uninstall_one() {
  local label="$1"
  for dir in "${HOME}/Library/LaunchAgents" "${HOME}/Library/LaunchAgents/disabled-ccc"; do
    local plist="${dir}/${label}.plist"
    if [[ -f "${plist}" ]]; then
      launchctl unload "${plist}" 2>/dev/null || true
      rm -f "${plist}"
      echo "removed ${plist}"
    fi
  done
}

case "${ACTION}" in
  install)
    write_plist "com.ccc.ops-daily-diff" "ccc-daily-diff-review.py"
    # docs 错开 15 分钟
    MINUTE=$(( (MINUTE + 15) % 60 ))
    if [[ ${MINUTE} -lt 15 ]]; then HOUR=$(( (HOUR + 1) % 24 )); fi
    write_plist "com.ccc.ops-docs-review" "ccc-daily-docs-review.py"
    ;;
  uninstall)
    uninstall_one "com.ccc.ops-daily-diff"
    uninstall_one "com.ccc.ops-docs-review"
    ;;
  status)
    echo "=== launchctl ==="
    launchctl list 2>/dev/null | grep -E 'com\.ccc\.ops-' || echo "(no loaded ops agents)"
    echo "=== plists ==="
    for label in com.ccc.ops-daily-diff com.ccc.ops-docs-review; do
      for dir in "${HOME}/Library/LaunchAgents" "${HOME}/Library/LaunchAgents/disabled-ccc"; do
        plist="${dir}/${label}.plist"
        if [[ -f "${plist}" ]]; then
          apply="no"
          if grep -q -- '--apply' "${plist}" 2>/dev/null; then apply="yes"; fi
          echo "${plist} apply_ammo=${apply}"
        fi
      done
    done
    ;;
  -h|--help) usage ;;
  *) usage; exit 2 ;;
esac
