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
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STAGE_DIR=""
BACKUP_DIR=""
ENV_BACKUP=""
SERVICE_BACKUP=""
PREVIOUSLY_ACTIVE=0
INSTALL_SUCCEEDED=0
ENV_EXISTED=0
SERVICE_EXISTED=0
CLI_EXISTED=0
CLI_BACKUP=""
APP_REPLACED=0
USER_CREATED=0
GROUP_CREATED=0
DATA_DIR_EXISTED=0
NON_INTERACTIVE=0
SKIP_AUTH=0
FORCE_CONFIG=0
CHECK_ONLY=0
SKIP_PACKAGES=0

log() {
  printf '[tg2bale] %s\n' "$*"
}

fail() {
  printf '[tg2bale] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: sudo bash setup.sh [options]

Options:
  --non-interactive  Read initial configuration from environment variables.
  --skip-auth        Install without creating or checking a Telegram session.
  --force-config     Replace /etc/telegram-to-bale.env.
  --check            Only validate OS compatibility and required source files.
  --skip-packages    Do not run apt-get; intended for pre-provisioned systems and CI.
  -h, --help         Show this help.
EOF
}

cleanup() {
  if [[ -n "${STAGE_DIR}" && -d "${STAGE_DIR}" ]]; then
    rm -rf -- "${STAGE_DIR}"
  fi
  if [[ "${INSTALL_SUCCEEDED}" -eq 1 && -n "${BACKUP_DIR}" && -d "${BACKUP_DIR}" ]]; then
    rm -rf -- "${BACKUP_DIR}"
  fi
  if [[ -n "${ENV_BACKUP}" && -f "${ENV_BACKUP}" ]]; then
    rm -f -- "${ENV_BACKUP}"
  fi
  if [[ -n "${SERVICE_BACKUP}" && -f "${SERVICE_BACKUP}" ]]; then
    rm -f -- "${SERVICE_BACKUP}"
  fi
  if [[ -n "${CLI_BACKUP}" && -f "${CLI_BACKUP}" ]]; then
    rm -f -- "${CLI_BACKUP}"
  fi
  return 0
}

rollback() {
  local exit_code=$?
  trap - ERR
  if [[ "${INSTALL_SUCCEEDED}" -eq 0 ]]; then
    log "Installation failed; attempting rollback."
    systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
    if [[ -n "${BACKUP_DIR}" && -d "${BACKUP_DIR}" ]]; then
      rm -rf -- "${APP_DIR}"
      mv -- "${BACKUP_DIR}" "${APP_DIR}"
    elif [[ "${APP_REPLACED}" -eq 1 ]]; then
      rm -rf -- "${APP_DIR}"
    fi
    if [[ -n "${ENV_BACKUP}" && -f "${ENV_BACKUP}" ]]; then
      cp -a -- "${ENV_BACKUP}" "${ENV_FILE}"
    elif [[ "${ENV_EXISTED}" -eq 0 ]]; then
      rm -f -- "${ENV_FILE}"
    fi
    if [[ -n "${SERVICE_BACKUP}" && -f "${SERVICE_BACKUP}" ]]; then
      cp -a -- "${SERVICE_BACKUP}" "${SERVICE_FILE}"
    elif [[ "${SERVICE_EXISTED}" -eq 0 ]]; then
      rm -f -- "${SERVICE_FILE}"
    fi
    if [[ -n "${CLI_BACKUP}" && -f "${CLI_BACKUP}" ]]; then
      cp -a -- "${CLI_BACKUP}" "${CLI_FILE}"
    elif [[ "${CLI_EXISTED}" -eq 0 ]]; then
      rm -f -- "${CLI_FILE}"
    fi
    systemctl daemon-reload >/dev/null 2>&1 || true
    if [[ "${PREVIOUSLY_ACTIVE}" -eq 1 ]]; then
      systemctl start "${SERVICE_NAME}" >/dev/null 2>&1 || true
    fi
    if [[ "${DATA_DIR_EXISTED}" -eq 0 ]]; then
      rm -rf -- "${DATA_DIR}"
    fi
    if [[ "${USER_CREATED}" -eq 1 ]]; then
      userdel "${APP_USER}" >/dev/null 2>&1 || true
    fi
    if [[ "${GROUP_CREATED}" -eq 1 ]]; then
      groupdel "${APP_GROUP}" >/dev/null 2>&1 || true
    fi
  fi
  cleanup
  exit "${exit_code}"
}

trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --non-interactive)
      NON_INTERACTIVE=1
      ;;
    --skip-auth)
      SKIP_AUTH=1
      ;;
    --force-config)
      FORCE_CONFIG=1
      ;;
    --check)
      CHECK_ONLY=1
      ;;
    --skip-packages)
      SKIP_PACKAGES=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
  shift
done

required_source_files=(
  main.py
  authenticate.py
  cli.py
  setup.py
  uninstall.sh
  requirements.txt
  VERSION
)

validate_source_tree() {
  local file
  for file in "${required_source_files[@]}"; do
    [[ -f "${SCRIPT_DIR}/${file}" ]] || fail "Missing source file: ${file}"
  done
}

detect_os() {
  [[ -r /etc/os-release ]] || fail "/etc/os-release is not available"
  # shellcheck disable=SC1091
  source /etc/os-release
  case "${ID:-}" in
    ubuntu)
      dpkg --compare-versions "${VERSION_ID:-0}" ge "22.04" \
        || fail "Ubuntu ${VERSION_ID:-unknown} is unsupported; use Ubuntu 22.04 or newer"
      ;;
    debian)
      dpkg --compare-versions "${VERSION_ID:-0}" ge "12" \
        || fail "Debian ${VERSION_ID:-unknown} is unsupported; use Debian 12 or newer"
      ;;
    *)
      fail "Unsupported distribution: ${ID:-unknown}. Only Debian and Ubuntu are supported"
      ;;
  esac
  log "Detected ${PRETTY_NAME:-${ID}}"
}

validate_source_tree
detect_os
command -v apt-get >/dev/null 2>&1 || fail "apt-get is required"
command -v dpkg >/dev/null 2>&1 || fail "dpkg is required"

if [[ "${CHECK_ONLY}" -eq 1 ]]; then
  log "Compatibility check passed."
  exit 0
fi

[[ "${EUID}" -eq 0 ]] || fail "Run this installer as root: sudo bash setup.sh"
command -v systemctl >/dev/null 2>&1 || fail "systemd is required"

install_packages() {
  log "Installing operating-system dependencies."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends \
    ca-certificates curl ffmpeg git python3 python3-pip python3-venv
}

ensure_service_user() {
  if [[ -d "${DATA_DIR}" ]]; then
    DATA_DIR_EXISTED=1
  fi
  if ! getent group "${APP_GROUP}" >/dev/null; then
    groupadd --system "${APP_GROUP}"
    GROUP_CREATED=1
  fi
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd \
      --system \
      --gid "${APP_GROUP}" \
      --home-dir "${DATA_DIR}" \
      --create-home \
      --shell /usr/sbin/nologin \
      "${APP_USER}"
    USER_CREATED=1
  fi
  install -d -m 0750 -o "${APP_USER}" -g "${APP_GROUP}" "${DATA_DIR}" "${DATA_DIR}/temp"
}

migrate_legacy_installation() {
  local legacy_dir=""
  if [[ ! -f "${ENV_FILE}" && -f "${SERVICE_FILE}" ]]; then
    legacy_dir="$(sed -n 's/^WorkingDirectory=//p' "${SERVICE_FILE}" | head -n 1)"
  fi
  if [[ -n "${legacy_dir}" && -d "${legacy_dir}" ]]; then
    if [[ -f "${legacy_dir}/.env" && ! -f "${ENV_FILE}" ]]; then
      log "Migrating legacy configuration from ${legacy_dir}/.env."
      install -m 0640 -o root -g "${APP_GROUP}" "${legacy_dir}/.env" "${ENV_FILE}"
      printf '\nTG2BALE_DATA_DIR=%s\n' "${DATA_DIR}" >> "${ENV_FILE}"
    fi
    if [[ -f "${legacy_dir}/session.session" && ! -f "${DATA_DIR}/telegram.session" ]]; then
      log "Migrating legacy Telegram session."
      install -m 0600 -o "${APP_USER}" -g "${APP_GROUP}" \
        "${legacy_dir}/session.session" "${DATA_DIR}/telegram.session"
    fi
  fi
}

prompt_value() {
  local variable_name=$1
  local prompt_text=$2
  local secret=${3:-0}
  local current_value=${!variable_name:-}

  if [[ -n "${current_value}" ]]; then
    printf -v "${variable_name}" '%s' "${current_value}"
    return
  fi
  if [[ "${NON_INTERACTIVE}" -eq 1 ]]; then
    fail "${variable_name} must be set for --non-interactive installation"
  fi
  if [[ "${secret}" -eq 1 ]]; then
    read -r -s -p "${prompt_text}" current_value
    printf '\n'
  else
    read -r -p "${prompt_text}" current_value
  fi
  [[ -n "${current_value}" ]] || fail "${variable_name} cannot be empty"
  [[ "${current_value}" != *$'\n'* && "${current_value}" != *$'\r'* ]] \
    || fail "${variable_name} contains an invalid newline"
  printf -v "${variable_name}" '%s' "${current_value}"
}

quote_env_value() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  printf '"%s"' "${value}"
}

set_runtime_setting() {
  local key=$1
  local value=$2
  local escaped
  escaped="$(quote_env_value "${value}")"
  if grep -qE "^${key}=" "${ENV_FILE}"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${escaped}" >> "${ENV_FILE}"
  fi
}

ensure_runtime_defaults() {
  set_runtime_setting TG2BALE_DATA_DIR "${DATA_DIR}"
  grep -qE '^TG2BALE_REQUEST_TIMEOUT=' "${ENV_FILE}" || printf 'TG2BALE_REQUEST_TIMEOUT=120\n' >> "${ENV_FILE}"
  grep -qE '^TG2BALE_MAX_RETRIES=' "${ENV_FILE}" || printf 'TG2BALE_MAX_RETRIES=3\n' >> "${ENV_FILE}"
  grep -qE '^TG2BALE_RETRY_BASE_SECONDS=' "${ENV_FILE}" || printf 'TG2BALE_RETRY_BASE_SECONDS=1\n' >> "${ENV_FILE}"
  grep -qE '^TG2BALE_WORKERS=' "${ENV_FILE}" || printf 'TG2BALE_WORKERS=1\n' >> "${ENV_FILE}"
  grep -qE '^TG2BALE_QUEUE_SIZE=' "${ENV_FILE}" || printf 'TG2BALE_QUEUE_SIZE=100\n' >> "${ENV_FILE}"
  grep -qE '^TG2BALE_TEXT_LIMIT=' "${ENV_FILE}" || printf 'TG2BALE_TEXT_LIMIT=4096\n' >> "${ENV_FILE}"
  grep -qE '^TG2BALE_LOG_LEVEL=' "${ENV_FILE}" || printf 'TG2BALE_LOG_LEVEL=INFO\n' >> "${ENV_FILE}"
  chown root:"${APP_GROUP}" "${ENV_FILE}"
  chmod 0640 "${ENV_FILE}"
}

write_configuration() {
  if [[ -f "${ENV_FILE}" && "${FORCE_CONFIG}" -eq 0 ]]; then
    log "Keeping existing configuration at ${ENV_FILE}."
    ensure_runtime_defaults
    return
  fi

  prompt_value API_ID "Telegram API ID: "
  [[ "${API_ID}" =~ ^[1-9][0-9]*$ ]] || fail "API_ID must be a positive integer"
  prompt_value API_HASH "Telegram API Hash: " 1
  prompt_value BALE_BOT_TOKEN "Bale Bot Token: " 1
  prompt_value BALE_CHAT_ID "Bale Channel Chat ID: "
  prompt_value SOURCE_CHANNELS "Telegram channels, comma-separated: "

  local temp_env
  temp_env="$(mktemp)"
  {
    printf 'API_ID=%s\n' "$(quote_env_value "${API_ID}")"
    printf 'API_HASH=%s\n' "$(quote_env_value "${API_HASH}")"
    printf 'BALE_BOT_TOKEN=%s\n' "$(quote_env_value "${BALE_BOT_TOKEN}")"
    printf 'BALE_CHAT_ID=%s\n' "$(quote_env_value "${BALE_CHAT_ID}")"
    printf 'SOURCE_CHANNELS=%s\n' "$(quote_env_value "${SOURCE_CHANNELS}")"
    printf 'TG2BALE_DATA_DIR=%s\n' "$(quote_env_value "${DATA_DIR}")"
    printf 'TG2BALE_REQUEST_TIMEOUT=120\n'
    printf 'TG2BALE_MAX_RETRIES=3\n'
    printf 'TG2BALE_RETRY_BASE_SECONDS=1\n'
    printf 'TG2BALE_WORKERS=1\n'
    printf 'TG2BALE_QUEUE_SIZE=100\n'
    printf 'TG2BALE_TEXT_LIMIT=4096\n'
    printf 'TG2BALE_LOG_LEVEL=INFO\n'
  } > "${temp_env}"
  install -m 0640 -o root -g "${APP_GROUP}" "${temp_env}" "${ENV_FILE}"
  rm -f -- "${temp_env}"
  ensure_runtime_defaults
}

stage_application() {
  STAGE_DIR="$(mktemp -d /opt/telegram-to-bale.stage.XXXXXX)"
  install -d -m 0755 "${STAGE_DIR}"
  install -m 0644 \
    "${SCRIPT_DIR}/main.py" \
    "${SCRIPT_DIR}/authenticate.py" \
    "${SCRIPT_DIR}/cli.py" \
    "${SCRIPT_DIR}/setup.py" \
    "${SCRIPT_DIR}/requirements.txt" \
    "${SCRIPT_DIR}/VERSION" \
    "${STAGE_DIR}/"
  install -m 0755 "${SCRIPT_DIR}/uninstall.sh" "${STAGE_DIR}/uninstall.sh"
  if [[ -f "${SCRIPT_DIR}/README.md" ]]; then
    install -m 0644 "${SCRIPT_DIR}/README.md" "${STAGE_DIR}/README.md"
  fi
  if [[ -f "${SCRIPT_DIR}/README.fa.md" ]]; then
    install -m 0644 "${SCRIPT_DIR}/README.fa.md" "${STAGE_DIR}/README.fa.md"
  fi
  for file in CHANGELOG.md SECURITY.md LICENSE .env.example; do
    if [[ -f "${SCRIPT_DIR}/${file}" ]]; then
      install -m 0644 "${SCRIPT_DIR}/${file}" "${STAGE_DIR}/${file}"
    fi
  done
}

activate_application() {
  if [[ -d "${APP_DIR}" ]]; then
    BACKUP_DIR="$(mktemp -d /opt/telegram-to-bale.backup.XXXXXX)"
    rmdir -- "${BACKUP_DIR}"
    mv -- "${APP_DIR}" "${BACKUP_DIR}"
  fi
  mv -- "${STAGE_DIR}" "${APP_DIR}"
  STAGE_DIR=""
  APP_REPLACED=1

  log "Creating isolated Python virtual environment."
  python3 -m venv "${APP_DIR}/.venv"
  "${APP_DIR}/.venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip
  "${APP_DIR}/.venv/bin/python" -m pip install --disable-pip-version-check -r "${APP_DIR}/requirements.txt"
}

write_service() {
  cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Telegram to Bale Forwarder
Documentation=https://github.com/ach1992/telegram-to-bale
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/main.py
Restart=on-failure
RestartSec=5s
TimeoutStopSec=30s
KillSignal=SIGINT
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${DATA_DIR}
ProtectControlGroups=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectClock=true
ProtectHostname=true
ProtectProc=invisible
ProcSubset=pid
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
RestrictNamespaces=true
RestrictRealtime=true
RestrictSUIDSGID=true
LockPersonality=true
CapabilityBoundingSet=
AmbientCapabilities=
SystemCallArchitectures=native

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "${SERVICE_FILE}"
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}" >/dev/null
}

write_cli() {
  cat > "${CLI_FILE}" <<EOF
#!/bin/sh
exec ${APP_DIR}/.venv/bin/python ${APP_DIR}/cli.py "\$@"
EOF
  chmod 0755 "${CLI_FILE}"
}

session_is_authorized() {
  runuser -u "${APP_USER}" -- \
    "${APP_DIR}/.venv/bin/python" "${APP_DIR}/authenticate.py" \
    --env-file "${ENV_FILE}" --check >/dev/null 2>&1
}

authorize_session() {
  if [[ "${SKIP_AUTH}" -eq 1 ]]; then
    log "Telegram authentication skipped; the service will remain stopped."
    return
  fi
  if session_is_authorized; then
    log "Existing Telegram session is authorized."
    return
  fi
  if [[ "${NON_INTERACTIVE}" -eq 1 ]]; then
    fail "No authorized Telegram session exists. Re-run interactively or use --skip-auth"
  fi

  local phone
  read -r -p "Telegram phone number in international format: " phone
  [[ -n "${phone}" ]] || fail "Telegram phone number cannot be empty"
  log "Starting Telegram authentication. Enter the login code and 2FA password if requested."
  runuser -u "${APP_USER}" -- \
    "${APP_DIR}/.venv/bin/python" "${APP_DIR}/authenticate.py" \
    --env-file "${ENV_FILE}" --phone "${phone}"
}

validate_installation() {
  runuser -u "${APP_USER}" -- \
    "${APP_DIR}/.venv/bin/python" "${APP_DIR}/main.py" \
    --env-file "${ENV_FILE}" --check-config

  if [[ "${SKIP_AUTH}" -eq 1 ]]; then
    systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
    log "Service installed but not started because Telegram authentication was skipped."
    return
  fi

  if session_is_authorized; then
    systemctl restart "${SERVICE_NAME}"
    sleep 2
    if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
      journalctl -u "${SERVICE_NAME}" -n 50 --no-pager >&2 || true
      fail "Service did not start successfully"
    fi
    log "Service is active."
  else
    systemctl stop "${SERVICE_NAME}" >/dev/null 2>&1 || true
    log "Service installed but not started because Telegram authentication is incomplete."
  fi
}

if [[ "${SKIP_PACKAGES}" -eq 0 ]]; then
  install_packages
else
  log "Skipping operating-system package installation."
fi
ensure_service_user

if [[ -f "${ENV_FILE}" ]]; then
  ENV_EXISTED=1
  ENV_BACKUP="$(mktemp)"
  cp -a "${ENV_FILE}" "${ENV_BACKUP}"
fi
if [[ -f "${SERVICE_FILE}" ]]; then
  SERVICE_EXISTED=1
  SERVICE_BACKUP="$(mktemp)"
  cp -a "${SERVICE_FILE}" "${SERVICE_BACKUP}"
fi
if [[ -f "${CLI_FILE}" ]]; then
  CLI_EXISTED=1
  CLI_BACKUP="$(mktemp)"
  cp -a "${CLI_FILE}" "${CLI_BACKUP}"
fi

trap rollback ERR

# Stop a legacy/current service before copying its SQLite session and replacing files.
if systemctl is-active --quiet "${SERVICE_NAME}"; then
  PREVIOUSLY_ACTIVE=1
  systemctl stop "${SERVICE_NAME}"
fi

# Migration mutates persistent state, so it runs only after rollback snapshots exist.
migrate_legacy_installation
write_configuration
stage_application
activate_application
chown -R root:root "${APP_DIR}"
chown -R "${APP_USER}:${APP_GROUP}" "${DATA_DIR}"
write_service
write_cli
authorize_session
validate_installation

INSTALL_SUCCEEDED=1
log "Installation completed."
log "Use: teltobale status | logs | restart | doctor | uninstall"
