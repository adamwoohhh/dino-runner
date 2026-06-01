#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ai-dino-in-terminal"
COMMAND_NAME="dino"
DEFAULT_VERSION="latest"
DEFAULT_REPO="https://github.com/adamwoohhh/agents-competition"

DINO_VERSION="${DINO_VERSION:-$DEFAULT_VERSION}"
DINO_REPO="${DINO_REPO:-$DEFAULT_REPO}"
DINO_INSTALL_SOURCE="${DINO_INSTALL_SOURCE:-github}"
DINO_HOME="${DINO_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/$APP_NAME}"
DINO_BIN_DIR="${DINO_BIN_DIR:-$HOME/.local/bin}"

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'install.sh: %s\n' "$*" >&2
  exit 1
}

find_python() {
  if [ -n "${PYTHON:-}" ]; then
    command -v "$PYTHON" >/dev/null 2>&1 || fail "PYTHON is set to '$PYTHON', but it was not found"
    printf '%s\n' "$PYTHON"
    return
  fi

  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  fail "Python 3.11+ is required, but no python3 executable was found"
}

require_python_311() {
  "$1" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required")
PY
}

download() {
  url="$1"
  output="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$output"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$output" "$url"
  else
    fail "curl or wget is required to download the release wheel"
  fi
}

resolve_latest_version() {
  command -v curl >/dev/null 2>&1 || fail "curl is required to resolve the latest GitHub release; set DINO_VERSION to install a fixed version"

  latest_url="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "$DINO_REPO/releases/latest")"
  latest_tag="${latest_url##*/}"
  [ "$latest_tag" != "$latest_url" ] || fail "could not resolve latest GitHub release tag"
  case "$latest_tag" in
    v*) ;;
    *) fail "latest GitHub release tag must start with 'v': $latest_tag" ;;
  esac

  latest_version="${latest_tag#v}"
  RELEASE_BASE_URL="${latest_url%/tag/*}/download/$latest_tag"

  DINO_VERSION="$latest_version"
  WHEEL_URL="$RELEASE_BASE_URL/ai_dino_in_terminal-${DINO_VERSION}-py3-none-any.whl"
}

uninstall() {
  rm -f "$DINO_BIN_DIR/$COMMAND_NAME"
  rm -rf "$DINO_HOME"
  log "Removed $COMMAND_NAME from $DINO_BIN_DIR and $DINO_HOME"
}

if [ "${1:-}" = "--uninstall" ]; then
  uninstall
  exit 0
fi

PYTHON_BIN="$(find_python)"
require_python_311 "$PYTHON_BIN"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [ -n "${DINO_WHEEL_PATH:-}" ]; then
  WHEEL_PATH="$DINO_WHEEL_PATH"
  if [ "$DINO_VERSION" = "latest" ]; then
    wheel_file="${WHEEL_PATH##*/}"
    parsed_version="${wheel_file#ai_dino_in_terminal-}"
    parsed_version="${parsed_version%-py3-none-any.whl}"
    if [ "$parsed_version" != "$wheel_file" ]; then
      DINO_VERSION="$parsed_version"
    fi
  fi
elif [ "$DINO_INSTALL_SOURCE" = "github" ]; then
  if [ "$DINO_VERSION" = "latest" ]; then
    resolve_latest_version
  else
    RELEASE_BASE_URL="$DINO_REPO/releases/download/v$DINO_VERSION"
    WHEEL_URL="$RELEASE_BASE_URL/ai_dino_in_terminal-${DINO_VERSION}-py3-none-any.whl"
  fi
  WHEEL_NAME="ai_dino_in_terminal-${DINO_VERSION}-py3-none-any.whl"
  WHEEL_PATH="$TMP_DIR/$WHEEL_NAME"
  log "Downloading $WHEEL_URL"
  download "$WHEEL_URL" "$WHEEL_PATH"
else
  fail "unsupported DINO_INSTALL_SOURCE='$DINO_INSTALL_SOURCE'; use 'github' or set DINO_WHEEL_PATH"
fi

[ -f "$WHEEL_PATH" ] || fail "wheel file not found: $WHEEL_PATH"

mkdir -p "$DINO_HOME" "$DINO_BIN_DIR"
"$PYTHON_BIN" -m venv "$DINO_HOME/venv"
"$DINO_HOME/venv/bin/python" -m pip install --no-index --force-reinstall "$WHEEL_PATH"
ln -sf "$DINO_HOME/venv/bin/$COMMAND_NAME" "$DINO_BIN_DIR/$COMMAND_NAME"

log "Installed $COMMAND_NAME $DINO_VERSION to $DINO_BIN_DIR/$COMMAND_NAME"
case ":$PATH:" in
  *":$DINO_BIN_DIR:"*) ;;
  *) log "Add $DINO_BIN_DIR to PATH if '$COMMAND_NAME' is not found." ;;
esac
