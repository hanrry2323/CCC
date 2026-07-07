#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "${SCRIPT_PATH}")"
CCC_HOME="$(realpath "${SCRIPT_DIR}/..")"

ACTION="install"
TARGET="ccc-exec-launcher.sh"
INTERVAL=300
LABEL_BASE="com.ccc"
LOG_DIR="${CCC_HOME}/.ccc/logs"
ENABLE_NOW=true
DRY_RUN=false
PHASE_ARG=""
PROMPT_ARG=""

usage() {
  cat <<EOU
Usage: $(basename "$0") [install|uninstall|status] [options]

Options:
  --target NAME      Script under CCC_HOME/scripts (default: ccc-exec-launcher.sh)
  --phase PHASE      phase-id for launcher (default: empty)
  --prompt FILE      prompt file for launcher (default: empty)
  --interval SEC     StartInterval seconds (default: 300 = 5min)
  --label PREFIX     Label prefix (default: com.ccc)
  --log-dir PATH     Log directory (default: \${CCC_HOME}/.ccc/logs)
  --no-enable        Write plist but do not launchctl load
  --dry-run          Print plist only, do not install
  -h, --help         Show this help

Examples:
  $(basename "$0") install
  $(basename "$0") install --target flywheel-scan.sh --interval 3600
  $(basename "$0") uninstall
  $(basename "$0") status
EOU
}

require_value() {
  [[ $# -ge 2 && -n "$2" ]] || { echo "Option $1 requires a value" >&2; exit 2; }
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    install|uninstall|status) ACTION="$1"; shift ;;
    --target)     require_value "$@"; TARGET="$2";     shift 2 ;;
    --phase)      require_value "$@"; PHASE_ARG="$2";   shift 2 ;;
    --prompt)     require_value "$@"; PROMPT_ARG="$2";  shift 2 ;;
    --interval)   require_value "$@"; INTERVAL="$2";   shift 2 ;;
    --label)      require_value "$@"; LABEL_BASE="$2"; shift 2 ;;
    --log-dir)    require_value "$@"; LOG_DIR="$2";    shift 2 ;;
    --no-enable)  ENABLE_NOW=false; shift ;;
    --dry-run)    DRY_RUN=true; shift ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

LABEL="${LABEL_BASE}.$(basename "${TARGET}" .sh)"
TARGET_PATH="${CCC_HOME}/scripts/${TARGET}"
LOG_OUT="${LOG_DIR}/$(basename "${TARGET}" .sh).out.log"
LOG_ERR="${LOG_DIR}/$(basename "${TARGET}" .sh).err.log"
PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST="${PLIST_DIR}/${LABEL}.plist"

ensure_target() {
  [[ -f "${TARGET_PATH}" ]] || { echo "Target not found: ${TARGET_PATH}" >&2; exit 1; }
  [[ -x "${TARGET_PATH}" ]] || chmod +x "${TARGET_PATH}"
}

do_install() {
  ensure_target
  mkdir -p "${LOG_DIR}" "${PLIST_DIR}"

  # 构 ProgramArguments
  # 如果是 ccc-exec-launcher.sh，watchdog 已内置在 launcher Step 1（红线 X3）
  # 直接调 launcher 即可，不用单独前置 watchdog
  local PROGRAM_ARGS
  if [[ "$(basename "${TARGET}")" == "ccc-exec-launcher.sh" ]]; then
    PROGRAM_ARGS="<string>${TARGET_PATH}</string>"
    [[ -n "${PHASE_ARG}" ]] && PROGRAM_ARGS="${PROGRAM_ARGS}
    <string>${PHASE_ARG}</string>"
    [[ -n "${PROMPT_ARG}" ]] && PROGRAM_ARGS="${PROGRAM_ARGS}
    <string>${PROMPT_ARG}</string>"
  else
    PROGRAM_ARGS="<string>${TARGET_PATH}</string>"
  fi

  local PLIST_CONTENT="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    ${PROGRAM_ARGS}
  </array>
  <key>WorkingDirectory</key>
  <string>${CCC_HOME}</string>
  <key>StartInterval</key>
  <integer>${INTERVAL}</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_OUT}</string>
  <key>StandardErrorPath</key>
  <string>${LOG_ERR}</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>"

  if ${DRY_RUN}; then
    echo "===== DRY RUN: ${PLIST} ====="
    echo "${PLIST_CONTENT}"
    echo "===== END DRY RUN ====="
    return 0
  fi

  echo "${PLIST_CONTENT}" > "${PLIST}"
  plutil -lint "${PLIST}" >/dev/null

  launchctl unload "${PLIST}" 2>/dev/null || true
  if ${ENABLE_NOW}; then
    launchctl load -w "${PLIST}"
  fi

  echo "Installed: ${PLIST}"
  echo "Logs:      ${LOG_OUT}"
  echo "           ${LOG_ERR}"
  echo "Interval:  ${INTERVAL}s"
}

do_uninstall() {
  if [[ -f "${PLIST}" ]]; then
    launchctl unload "${PLIST}" 2>/dev/null || true
    rm -f "${PLIST}"
    echo "Uninstalled: ${PLIST}"
  else
    echo "Not installed: ${PLIST}"
  fi
}

do_status() {
  if [[ ! -f "${PLIST}" ]]; then
    echo "Plist absent: ${PLIST}"
    return
  fi
  local uid
  uid="$(id -u)"
  launchctl print "user/${uid}/${LABEL}" 2>/dev/null \
    || launchctl print "gui/${uid}/${LABEL}" 2>/dev/null \
    || true
}

case "${ACTION}" in
  install)   do_install ;;
  uninstall) do_uninstall ;;
  status)    do_status ;;
esac
