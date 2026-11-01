#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEBUG_LOG="${PRIVEOPDF_DEBUG_LOG:-0}"
MAX_LOG_BYTES=524288
MAX_LOG_FILES=5
readonly BROKER_HOME="/home/priveopdf"

if [[ "${1:-}" == "--debug-log" ]]; then
  DEBUG_LOG=1
  shift
fi

# F11: a path is masked to its end, spaces included: anything under the home
# directory (whatever the file name), any name ending in .pdf wherever it is
# (absolute or relative) and any other absolute path.
redact_stream() {
  sed -u -E \
    -e "s|${PROJECT//|/\\|}|<project>|g" \
    -e "s|${HOME//|/\\|}|~|g" \
    -e 's#((password|passwd|pwd|mot[[:space:]_-]*de[[:space:]_-]*passe)[[:space:]]*[:=][[:space:]]*)[^[:space:]]+#\1<redacted>#Ig' \
    -e 's#((client|customer|display_name|document_name)[[:space:]]*[:=][[:space:]]*)[^[:space:]]+#\1<redacted>#Ig' \
    -e 's#[^[:space:]]*(password|passwd|confidentiel|confidential)[^[:space:]]*#<redacted>#Ig' \
    -e 's#~(/[^/"'"'"'[:cntrl:]]*)+#<redacted-home-path>#g' \
    -e 's#(^|[[:space:]="'"'"'(])[^[:space:]"'"'"'(=]*(/[^/"'"'"'[:cntrl:]]*)*\.pdf#\1<redacted-pdf-path>#Ig' \
    -e 's#(^|[[:space:]="'"'"'(])/[^"'"'"'[:cntrl:]]+#\1<redacted-path>#g'
}

# F04: launched from the menu, there is no terminal; the reason is shown, in
# French or English after the desktop language (Codex review of CA4).
notify_failure() {
  local message="$2"
  case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in
    fr*) message="$1" ;;
  esac
  printf '%s\n' "$message" >&2
  if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    return 0
  fi
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title='PriveoPDF' --text="$message" >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send --urgency=critical 'PriveoPDF' "$message" >/dev/null 2>&1 || true
  fi
}

rotate_logs() {
  local log_file=$1
  [[ -f "$log_file" ]] || return 0
  local size
  size=$(stat -c '%s' "$log_file" 2>/dev/null || printf '0')
  ((size < MAX_LOG_BYTES)) && return 0
  local index
  for ((index = MAX_LOG_FILES - 1; index >= 1; index--)); do
    [[ -f "${log_file}.${index}" ]] && mv -f "${log_file}.${index}" "${log_file}.$((index + 1))"
  done
  mv -f "$log_file" "${log_file}.1"
}

enable_debug_log() {
  local state_root=${XDG_STATE_HOME:-"$HOME/.local/state"}
  local log_dir="$state_root/priveopdf"
  local log_file="$log_dir/launcher.log"
  install -d -m 0700 "$log_dir"
  rotate_logs "$log_file"
  : >>"$log_file"
  chmod 0600 "$log_file"
  exec > >(tee >(redact_stream >>"$log_file")) 2>&1
  printf '%s\n' "PriveoPDF debug logging enabled (sensitive values redacted)."
}

if [[ "${PRIVEOPDF_SOURCE_ONLY:-0}" == "1" ]]; then
  if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return 0
  fi
  exit 0
fi

if [[ "$DEBUG_LOG" == "1" ]]; then
  enable_debug_log
fi

if ! cd "$PROJECT"; then
  notify_failure "PriveoPDF ne peut pas démarrer : dossier du programme introuvable." \
    "PriveoPDF cannot start: program folder not found."
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  notify_failure "PriveoPDF ne peut pas démarrer : installation incomplète (relancer l'installation)." \
    "PriveoPDF cannot start: incomplete installation (run the installation again)."
  exit 1
fi

export PYTHONPATH=src

if [[ "$(uname -s)" != "Linux" ]]; then
  export PRIVEOPDF_ALLOW_UNSANDBOXED_DEV=1
  exec .venv/bin/python -P -m priveopdf.app.main "$@"
fi

if ! command -v bwrap >/dev/null 2>&1; then
  notify_failure "PriveoPDF ne peut pas démarrer sans son isolation : installer Bubblewrap (sudo apt install bubblewrap). Code : network_isolation_unavailable." \
    "PriveoPDF cannot start without its isolation: install Bubblewrap (sudo apt install bubblewrap). Code: network_isolation_unavailable."
  exit 78
fi
if ! bwrap --die-with-parent --unshare-net --ro-bind / / -- /bin/true 2>/dev/null; then
  notify_failure "PriveoPDF ne peut pas démarrer : Bubblewrap ne peut pas isoler le réseau sur cet ordinateur. Code : network_isolation_unavailable." \
    "PriveoPDF cannot start: Bubblewrap cannot isolate the network on this computer. Code: network_isolation_unavailable."
  exit 78
fi

RUNTIME_BASE="${XDG_RUNTIME_DIR:-/tmp}"
if [[ ! -d "$RUNTIME_BASE" || ! -O "$RUNTIME_BASE" ]]; then
  RUNTIME_BASE="/tmp"
fi
RUNTIME_BASE="$(cd "$RUNTIME_BASE" && pwd -P)"
SESSION_DIR="$(mktemp -d "$RUNTIME_BASE/priveopdf-runtime.XXXXXXXX")"
chmod 0700 "$SESSION_DIR"
BROKER_SOCKET="$SESSION_DIR/ipc/update-broker.sock"
BROKER_PID=""
MEMORY_BROKER_PID=""
OPENER_PID=""
BROKER_GIT_ASKPASS=""

prepare_broker_github_askpass() {
  # Public snapshots omit the private updater and never need GitHub credentials.
  [[ -e "$PROJECT/.git" && -f "$PROJECT/tools/update_from_github.sh" ]] || return 1
  local gh_bin=""
  local token_file="$SESSION_DIR/broker-home/github-token"
  local askpass_file="$SESSION_DIR/broker-home/github-askpass.sh"
  local candidate
  for candidate in /usr/bin/gh /usr/local/bin/gh; do
    if [[ -f "$candidate" && -x "$candidate" && ! -L "$candidate" ]]; then
      gh_bin="$candidate"
      break
    fi
  done
  [[ -n "$gh_bin" ]] || return 1
  if ! /usr/bin/env -u GH_TOKEN -u GITHUB_TOKEN \
    "$gh_bin" auth token >"$token_file" 2>/dev/null; then
    rm -f -- "$token_file"
    return 1
  fi
  [[ -s "$token_file" && "$(stat -c '%s' "$token_file")" -le 4096 ]] || {
    rm -f -- "$token_file"
    return 1
  }
  chmod 0600 "$token_file"
  # shellcheck disable=SC2016 # $1 belongs to the generated AskPass script
  printf '%s\n' \
    '#!/bin/sh' \
    'case "$1" in' \
    '  *Username*) printf "%s\\n" "x-access-token" ;;' \
    "  *Password*) exec /bin/cat '$BROKER_HOME/github-token' ;;" \
    '  *) exit 1 ;;' \
    'esac' >"$askpass_file"
  chmod 0700 "$askpass_file"
  BROKER_GIT_ASKPASS="$BROKER_HOME/github-askpass.sh"
}

stop_helpers() {
  local pid
  for pid in "$BROKER_PID" "$MEMORY_BROKER_PID" "$OPENER_PID"; do
    [[ -n "$pid" ]] || continue
    kill "$pid" >/dev/null 2>&1 || true
    wait "$pid" >/dev/null 2>&1 || true
  done
}

# shellcheck disable=SC2317,SC2329 # invoked indirectly by the EXIT/signal traps below
cleanup_runtime() {
  local status=$?
  trap - EXIT INT TERM HUP
  stop_helpers
  rm -rf -- "$SESSION_DIR"
  exit "$status"
}
trap cleanup_runtime EXIT INT TERM HUP

install -d -m 0700 \
  "$SESSION_DIR/ipc" \
  "$SESSION_DIR/memory-ipc" \
  "$SESSION_DIR/broker-home" \
  "$SESSION_DIR/broker-home/cache" \
  "$SESSION_DIR/broker-home/config" \
  "$SESSION_DIR/broker-home/data" \
  "$SESSION_DIR/broker-home/state" \
  "$SESSION_DIR/broker-tmp" \
  "$SESSION_DIR/document-tmp" \
  "$SESSION_DIR/document-tmp/priveopdf-ipc"

prepare_broker_github_askpass || true

BROKER_COMMAND=(
  bwrap
  --die-with-parent
  --new-session
  --unshare-ipc
  --unshare-pid
  --unshare-uts
  --proc /proc
  --dev /dev
  --dir /app
  --bind "$PROJECT" /app
  --dir /run
  --dir /run/priveopdf
  --bind "$SESSION_DIR/ipc" /run/priveopdf
  --dir /home
  --dir "$BROKER_HOME"
  --bind "$SESSION_DIR/broker-home" "$BROKER_HOME"
  --bind "$SESSION_DIR/broker-tmp" /tmp
  --ro-bind /usr /usr
  --ro-bind /bin /bin
  --clearenv
  --setenv HOME "$BROKER_HOME"
  --setenv LANG C.UTF-8
  --setenv LC_ALL C.UTF-8
  --setenv PATH /app/.venv/bin:/usr/bin:/bin
  --setenv PYTHONPATH /app/src
  --setenv TMPDIR /tmp
  --setenv XDG_CACHE_HOME "$BROKER_HOME/cache"
  --setenv XDG_CONFIG_HOME "$BROKER_HOME/config"
  --setenv XDG_DATA_HOME "$BROKER_HOME/data"
  --setenv XDG_RUNTIME_DIR /run/priveopdf
  --setenv XDG_STATE_HOME "$BROKER_HOME/state"
)
if [[ -n "$BROKER_GIT_ASKPASS" ]]; then
  BROKER_COMMAND+=(--setenv PRIVEOPDF_UPDATE_GIT_ASKPASS "$BROKER_GIT_ASKPASS")
fi
for system_path in /lib /lib64; do
  [[ -e "$system_path" ]] && BROKER_COMMAND+=(--ro-bind "$system_path" "$system_path")
done
BROKER_COMMAND+=(--dir /etc)
for system_path in /etc/hosts /etc/nsswitch.conf /etc/resolv.conf /etc/ssl; do
  [[ -e "$system_path" ]] && BROKER_COMMAND+=(--ro-bind "$system_path" "$system_path")
done
# Mount only the selected display endpoints; do not pass the desktop runtime
# directory or its session-bus/agent sockets through these display bindings.
DISPLAY_MOUNTS=(--perms 0700 --dir /run/priveopdf-display)
DISPLAY_ENV=(--setenv XDG_RUNTIME_DIR /run/priveopdf-display)
if [[ "${DISPLAY:-}" =~ ^(unix)?:([0-9]+)(\.[0-9]+)?$ ]]; then
  X11_SOCKET="/tmp/.X11-unix/X${BASH_REMATCH[2]}"
  if [[ -S "$X11_SOCKET" ]]; then
    DISPLAY_MOUNTS+=(--ro-bind "$X11_SOCKET" "$X11_SOCKET")
    DISPLAY_ENV+=(--setenv DISPLAY "$DISPLAY")
    DISPLAY_AUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
    if [[ -f "$DISPLAY_AUTHORITY" ]]; then
      DISPLAY_MOUNTS+=(--ro-bind "$DISPLAY_AUTHORITY" /run/priveopdf-display/Xauthority)
      DISPLAY_ENV+=(--setenv XAUTHORITY /run/priveopdf-display/Xauthority)
    fi
  fi
fi
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
  if [[ "$WAYLAND_DISPLAY" == /* ]]; then
    WAYLAND_SOCKET="$WAYLAND_DISPLAY"
  else
    WAYLAND_SOCKET="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/$WAYLAND_DISPLAY"
  fi
  if [[ -S "$WAYLAND_SOCKET" ]]; then
    DISPLAY_MOUNTS+=(--ro-bind "$WAYLAND_SOCKET" /run/priveopdf-display/wayland.sock)
    DISPLAY_ENV+=(--setenv WAYLAND_DISPLAY wayland.sock)
  fi
fi
if [[ -n "${QT_QPA_PLATFORM:-}" ]]; then
  DISPLAY_ENV+=(--setenv QT_QPA_PLATFORM "$QT_QPA_PLATFORM")
fi
BROKER_COMMAND+=("${DISPLAY_MOUNTS[@]}" "${DISPLAY_ENV[@]}")
BROKER_COMMAND+=(
  --
  /app/.venv/bin/python -P -m priveopdf.app.network_broker
  --socket /run/priveopdf/update-broker.sock
  --project-root /app
)
"${BROKER_COMMAND[@]}" &
BROKER_PID=$!

for _attempt in {1..100}; do
  [[ -S "$BROKER_SOCKET" ]] && break
  kill -0 "$BROKER_PID" >/dev/null 2>&1 || {
    printf '%s\n' "Erreur : le broker de mise à jour isolé n'a pas démarré." >&2
    exit 78
  }
  sleep 0.05
done
[[ -S "$BROKER_SOCKET" ]] || {
  printf '%s\n' "Erreur : le broker de mise à jour isolé est indisponible." >&2
  exit 78
}

# Separate, network-isolated memory helper; never reuse the update broker.
# Its absence blocks photocopy only, preserving the other PDF tools.
"$PROJECT/.venv/bin/python" -P -m priveopdf.workers.render_memory_broker \
  --socket "$SESSION_DIR/memory-ipc/memory.sock" >/dev/null 2>&1 &
MEMORY_BROKER_PID=$!
for _attempt in {1..100}; do
  [[ -S "$SESSION_DIR/memory-ipc/memory.sock" ]] && break
  kill -0 "$MEMORY_BROKER_PID" >/dev/null 2>&1 || break
  sleep 0.02
done

# Outside every sandbox: opens only the release page the broker verified, with
# the user's browser and desktop settings (src/priveopdf/app/release_opener.py).
"$PROJECT/.venv/bin/python" -P -m priveopdf.app.release_opener \
  --dir "$SESSION_DIR/ipc" >/dev/null 2>&1 &
OPENER_PID=$!

for xdg_variable in XDG_CONFIG_HOME XDG_CACHE_HOME XDG_DATA_HOME XDG_STATE_HOME; do
  xdg_value="${!xdg_variable:-}"
  if [[ -n "$xdg_value" ]]; then
    install -d -m 0700 "$xdg_value"
  fi
done

DOCUMENT_COMMAND=(
  bwrap
  --die-with-parent
  --new-session
  --unshare-net
  --unshare-ipc
  --unshare-pid
  --unshare-uts
  --ro-bind / /
  --proc /proc
  --dev /dev
  --bind "$HOME" "$HOME"
  --bind "$SESSION_DIR/document-tmp" /tmp
  --tmpfs /run
  --ro-bind "$BROKER_SOCKET" /tmp/priveopdf-ipc/update-broker.sock
  # Hide the host-side session even if XDG_RUNTIME_DIR points inside HOME.
  --tmpfs "$SESSION_DIR"
  --clearenv
  --setenv HOME "$HOME"
  --setenv LANG "${LANG:-C.UTF-8}"
  --setenv LC_ALL "${LC_ALL:-C.UTF-8}"
  --setenv PATH "$PROJECT/.venv/bin:/usr/bin:/bin"
  --setenv PRIVEOPDF_DOCUMENT_SANDBOX 1
  --setenv PRIVEOPDF_UPDATE_BROKER_SOCKET /tmp/priveopdf-ipc/update-broker.sock
  --setenv PYTHONPATH "$PROJECT/src"
  --setenv TMPDIR /tmp
)
for variable in \
  QT_SCALE_FACTOR \
  XDG_CONFIG_HOME XDG_CACHE_HOME XDG_DATA_HOME XDG_STATE_HOME \
  PRIVEOPDF_DEV PRIVEOPDF_OPEN_DIR \
  PRIVEOPDF_BETA PRIVEOPDF_BETA_ROOT PRIVEOPDF_BETA_DIR \
  PRIVEOPDF_BETA_INTEGRATION_MANIFEST PRIVEOPDF_BETA_CHECKLIST_STATE; do
  value="${!variable:-}"
  [[ -n "$value" ]] && DOCUMENT_COMMAND+=(--setenv "$variable" "$value")
done
if [[ -S "$SESSION_DIR/memory-ipc/memory.sock" ]]; then
  DOCUMENT_COMMAND+=(
    --ro-bind "$SESSION_DIR/memory-ipc/memory.sock" /tmp/priveopdf-ipc/memory.sock
    --setenv PRIVEOPDF_RENDER_BROKER_SOCKET /tmp/priveopdf-ipc/memory.sock
  )
fi
DOCUMENT_COMMAND+=("${DISPLAY_MOUNTS[@]}" "${DISPLAY_ENV[@]}")
DOCUMENT_COMMAND+=(-- "$PROJECT/.venv/bin/python" -P -m priveopdf.app.main "$@")

set +e
"${DOCUMENT_COMMAND[@]}"
DOCUMENT_STATUS=$?
set -e

SOURCE_REQUEST="$SESSION_DIR/ipc/source-install.request"
if [[ -e "$SOURCE_REQUEST" || -L "$SOURCE_REQUEST" ]]; then
  [[ -f "$SOURCE_REQUEST" && ! -L "$SOURCE_REQUEST" && -O "$SOURCE_REQUEST" ]] || {
    printf '%s\n' "Erreur : demande de mise à jour invalide." >&2
    exit 78
  }
  [[ "$(stat -c '%a' "$SOURCE_REQUEST")" == "600" ]] || {
    printf '%s\n' "Erreur : permissions de mise à jour invalides." >&2
    exit 78
  }
  [[ "$(stat -c '%s' "$SOURCE_REQUEST")" -le 64 ]] || {
    printf '%s\n' "Erreur : demande de mise à jour trop grande." >&2
    exit 78
  }
  mapfile -t SOURCE_REQUEST_LINES <"$SOURCE_REQUEST"
  [[ "${#SOURCE_REQUEST_LINES[@]}" -eq 2 ]] || {
    printf '%s\n' "Erreur : format de mise à jour invalide." >&2
    exit 78
  }
  SOURCE_PARENT_PID="${SOURCE_REQUEST_LINES[0]}"
  SOURCE_TARGET_REVISION="${SOURCE_REQUEST_LINES[1]}"
  [[ "$SOURCE_PARENT_PID" =~ ^[1-9][0-9]*$ ]] || exit 78
  [[ "$SOURCE_TARGET_REVISION" =~ ^[0-9a-f]{40}$ ]] || exit 78

  stop_helpers
  rm -rf -- "$SESSION_DIR"
  trap - EXIT INT TERM HUP

  HELPER_ENV=(
    /usr/bin/env -i
    HOME="$HOME"
    LANG="${LANG:-C.UTF-8}"
    LC_ALL="${LC_ALL:-C.UTF-8}"
    PATH="$PROJECT/.venv/bin:/usr/bin:/bin"
    PYTHONPATH="$PROJECT/src"
  )
  for variable in \
    DISPLAY XAUTHORITY WAYLAND_DISPLAY QT_QPA_PLATFORM QT_SCALE_FACTOR \
    XDG_CONFIG_HOME XDG_CACHE_HOME XDG_DATA_HOME XDG_RUNTIME_DIR XDG_STATE_HOME \
    PRIVEOPDF_DEV PRIVEOPDF_BETA; do
    value="${!variable:-}"
    [[ -n "$value" ]] && HELPER_ENV+=("$variable=$value")
  done
  exec "${HELPER_ENV[@]}" "$PROJECT/.venv/bin/python" -P \
    -m priveopdf.app.source_update_helper \
    --parent-pid "$SOURCE_PARENT_PID" \
    --target-revision "$SOURCE_TARGET_REVISION"
fi

exit "$DOCUMENT_STATUS"
