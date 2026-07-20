# shellcheck shell=bash
# Shared remote helper for Hub-Shell smokes.
# Source after SERVER is set:
#   # shellcheck source=scripts/_smoke_remote.sh
#   source "$(dirname "$0")/_smoke_remote.sh"
#
# When CCC_SERVER is loopback, default remote to 127.0.0.1 so gate can run
# on Mac2017 itself without resolving hostname "mac2017".

_SMOKE_SERVER="${SERVER:-${CCC_SERVER:-}}"
if [[ -z "${CCC_REMOTE_HOST:-}" ]]; then
  case "${_SMOKE_SERVER}" in
    *127.0.0.1*|*localhost*) export CCC_REMOTE_HOST="127.0.0.1" ;;
    *) export CCC_REMOTE_HOST="mac2017" ;;
  esac
fi
SMOKE_REMOTE_HOST="${CCC_REMOTE_HOST}"

smoke_remote() {
  ssh -o ConnectTimeout=8 -o BatchMode=yes "${SMOKE_REMOTE_HOST}" "$@"
}
