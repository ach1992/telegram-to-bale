#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n "${ROOT_DIR}/install.sh"
bash -n "${ROOT_DIR}/setup.sh"
bash -n "${ROOT_DIR}/uninstall.sh"
bash "${ROOT_DIR}/setup.sh" --check

if grep -R --line-number --fixed-strings -- '--break-system-packages' \
  "${ROOT_DIR}/install.sh" "${ROOT_DIR}/setup.sh" "${ROOT_DIR}/requirements.txt"; then
  printf 'Forbidden --break-system-packages option found.\n' >&2
  exit 1
fi

printf 'Shell smoke tests passed.\n'
