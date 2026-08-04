#!/usr/bin/env bash
set -Eeuo pipefail

APP_USER="tg2bale"
APP_GROUP="tg2bale"
APP_DIR="/opt/telegram-to-bale"
DATA_DIR="/var/lib/tg2bale"
ENV_FILE="/etc/telegram-to-bale.env"
SERVICE_NAME="tg2bale.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
CLI_FILE="/usr/local/bin/teltobale"
PURGE=0
ASSUME_YES=0

usage() {
  cat <<'EOF'
Usage: sudo bash uninstall.sh [--purge] [--yes]

Without --purge, configuration and Telegram session data are preserved.
With --purge, configuration, session data, and the service user are deleted.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge)
      PURGE=1
      ;;
    --yes)
      ASSUME_YES=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

[[ "${EUID}" -eq 0 ]] || {
  printf 'Run the uninstaller as root.\n' >&2
  exit 1
}

if [[ "${ASSUME_YES}" -eq 0 ]]; then
  if [[ "${PURGE}" -eq 1 ]]; then
    prompt="Remove the application, configuration, and Telegram session permanently? [y/N] "
  else
    prompt="Remove the application but preserve configuration and session data? [y/N] "
  fi
  read -r -p "${prompt}" answer
  [[ "${answer}" =~ ^[Yy]$ ]] || {
    printf 'Uninstall cancelled.\n'
    exit 0
  }
fi

systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
systemctl disable "${SERVICE_NAME}" >/dev/null 2>&1 || true
rm -f -- "${SERVICE_FILE}" "${CLI_FILE}"
systemctl daemon-reload
systemctl reset-failed "${SERVICE_NAME}" >/dev/null 2>&1 || true
rm -rf -- "${APP_DIR}"

if [[ "${PURGE}" -eq 1 ]]; then
  rm -f -- "${ENV_FILE}"
  rm -rf -- "${DATA_DIR}"
  if id -u "${APP_USER}" >/dev/null 2>&1; then
    userdel "${APP_USER}"
  fi
  if getent group "${APP_GROUP}" >/dev/null 2>&1; then
    groupdel "${APP_GROUP}" >/dev/null 2>&1 || true
  fi
  printf 'Application and all persistent data were removed.\n'
else
  printf 'Application removed. Preserved: %s and %s\n' "${ENV_FILE}" "${DATA_DIR}"
fi
