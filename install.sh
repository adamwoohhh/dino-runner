#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ai-dino-in-terminal"
COMMAND_NAME="dino"
DEFAULT_VERSION="0.1.1"
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

WHEEL_NAME="ai_dino_in_terminal-${DINO_VERSION}-py3-none-any.whl"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [ -n "${DINO_WHEEL_PATH:-}" ]; then
  WHEEL_PATH="$DINO_WHEEL_PATH"
elif [ "$DINO_INSTALL_SOURCE" = "github" ]; then
  WHEEL_PATH="$TMP_DIR/$WHEEL_NAME"
  RELEASE_BASE_URL="$DINO_REPO/releases/download/v$DINO_VERSION"
  WHEEL_URL="$RELEASE_BASE_URL/$WHEEL_NAME"
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
