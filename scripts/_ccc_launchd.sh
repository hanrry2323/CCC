# _ccc_launchd.sh — shared launchd helpers for CCC install scripts (v0.39.1)
# Source from install-*.sh after CCC_HOME is set.
#
# Policy: never launchctl load/bootstrap while control=disabled.
# Plists stage under ~/Library/LaunchAgents/disabled-ccc/ unless --start.

: "${CCC_HOME:?CCC_HOME must be set before sourcing _ccc_launchd.sh}"

CCC_PLIST_ACTIVE="${HOME}/Library/LaunchAgents"
CCC_PLIST_STAGED="${HOME}/Library/LaunchAgents/disabled-ccc"

_ccc_control_enabled() {
  PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -c "from _ccc_control import is_enabled; raise SystemExit(0 if is_enabled() else 1)" 2>/dev/null
}

# Stage or activate a plist. Engine requires control=enabled; UI requires ui|enabled.
# Usage: ccc_launchd_finalize LABEL PLIST_PATH [--start] [--ui|--engine]
ccc_launchd_finalize() {
  local label="$1"
  local plist="$2"
  local do_start=0
  local kind="engine"  # engine | ui
  shift 2 || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --start) do_start=1 ;;
      --ui) kind="ui" ;;
      --engine) kind="engine" ;;
    esac
    shift
  done

  mkdir -p "$CCC_PLIST_STAGED" "$CCC_PLIST_ACTIVE"
  local uid
  uid="$(id -u)"

  launchctl bootout "gui/${uid}/${label}" 2>/dev/null || true

  local allowed=0
  if [[ "$kind" == "ui" ]]; then
    PYTHONPATH="${CCC_HOME}/scripts${PYTHONPATH:+:$PYTHONPATH}" \
      python3 -c "from _ccc_control import may_start_ui; raise SystemExit(0 if may_start_ui() else 1)" 2>/dev/null \
      && allowed=1 || allowed=0
  else
    _ccc_control_enabled && allowed=1 || allowed=0
  fi

  if [[ "$do_start" != "1" ]] || [[ "$allowed" != "1" ]]; then
    local staged="${CCC_PLIST_STAGED}/$(basename "$plist")"
    if [[ "$(cd "$(dirname "$plist")" && pwd)" != "$(cd "$CCC_PLIST_STAGED" && pwd)" ]]; then
      mv -f "$plist" "$staged"
      plist="$staged"
    fi
    rm -f "${CCC_PLIST_ACTIVE}/$(basename "$plist")"
    echo "  ○ ${label} staged (not loaded) → ${plist}"
    if [[ "$kind" == "ui" ]]; then
      echo "    UI 常驻: bash ${CCC_HOME}/scripts/ccc-autostart-guard.sh ui --start"
      echo "    前台开发: bash ${CCC_HOME}/scripts/ccc-hub-dev.sh"
    else
      echo "    enable: bash ${CCC_HOME}/scripts/ccc-autostart-guard.sh enable --start"
    fi
    return 0
  fi

  local active="${CCC_PLIST_ACTIVE}/$(basename "$plist")"
  if [[ "$plist" != "$active" ]]; then
    mv -f "$plist" "$active"
    plist="$active"
  fi
  launchctl enable "gui/${uid}/${label}" 2>/dev/null || true
  launchctl bootstrap "gui/${uid}" "$plist" 2>/dev/null \
    || launchctl load -w "$plist" 2>/dev/null \
    || true
  echo "  ✓ ${label} loaded"
}
