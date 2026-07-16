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

# Stage or activate a plist file that already exists at $1 (absolute path written by caller).
# Usage: ccc_launchd_finalize LABEL PLIST_PATH [--start]
ccc_launchd_finalize() {
  local label="$1"
  local plist="$2"
  local do_start=0
  [[ "${3:-}" == "--start" ]] && do_start=1

  mkdir -p "$CCC_PLIST_STAGED" "$CCC_PLIST_ACTIVE"
  local uid
  uid="$(id -u)"

  # Always bootout first (idempotent)
  launchctl bootout "gui/${uid}/${label}" 2>/dev/null || true

  if [[ "$do_start" != "1" ]] || ! _ccc_control_enabled; then
    # Keep out of active LaunchAgents — stage only
    local staged="${CCC_PLIST_STAGED}/$(basename "$plist")"
    if [[ "$(cd "$(dirname "$plist")" && pwd)" != "$(cd "$CCC_PLIST_STAGED" && pwd)" ]]; then
      mv -f "$plist" "$staged"
      plist="$staged"
    fi
    # Remove stray active copy if any
    rm -f "${CCC_PLIST_ACTIVE}/$(basename "$plist")"
    echo "  ○ ${label} staged (not loaded) → ${plist}"
    echo "    enable: bash ${CCC_HOME}/scripts/ccc-autostart-guard.sh enable --start"
    return 0
  fi

  # Active path: ensure in LaunchAgents and bootstrap
  local active="${CCC_PLIST_ACTIVE}/$(basename "$plist")"
  if [[ "$plist" != "$active" ]]; then
    mv -f "$plist" "$active"
    plist="$active"
  fi
  launchctl bootstrap "gui/${uid}" "$plist" 2>/dev/null \
    || launchctl load -w "$plist" 2>/dev/null \
    || true
  echo "  ✓ ${label} loaded"
}
