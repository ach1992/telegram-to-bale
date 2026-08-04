#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY="ach1992/telegram-to-bale"
REF="${TG2BALE_REF:-main}"
TEMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf -- "${TEMP_DIR}"
}
trap cleanup EXIT

fail() {
  printf '[tg2bale] ERROR: %s\n' "$*" >&2
  exit 1
}

[[ "${EUID}" -eq 0 ]] || fail "Run as root: curl ... | sudo bash, or sudo bash install.sh"

if ! command -v curl >/dev/null 2>&1 || ! command -v tar >/dev/null 2>&1; then
  command -v apt-get >/dev/null 2>&1 || fail "curl and tar are required"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends ca-certificates curl tar
fi

archive_url="https://codeload.github.com/${REPOSITORY}/tar.gz/${REF}"
printf '[tg2bale] Downloading %s at ref %s.\n' "${REPOSITORY}" "${REF}"
curl \
  --fail \
  --location \
  --silent \
  --show-error \
  --retry 3 \
  --retry-all-errors \
  "${archive_url}" \
  -o "${TEMP_DIR}/source.tar.gz"

tar -xzf "${TEMP_DIR}/source.tar.gz" --strip-components=1 -C "${TEMP_DIR}"
[[ -f "${TEMP_DIR}/setup.sh" ]] || fail "Downloaded archive does not contain setup.sh"
bash "${TEMP_DIR}/setup.sh" "$@"
