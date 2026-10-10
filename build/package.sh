#!/bin/sh
# Portable shortcut for Linux/macOS. On Windows: python build/package.py
set -eu
exec "${PYTHON:-python3}" "$(dirname "$0")/package.py" "$@"
