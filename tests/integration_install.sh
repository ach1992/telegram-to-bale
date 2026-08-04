#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FAKE_BIN="$(mktemp -d)"

cleanup() {
  rm -rf -- "${FAKE_BIN}"
}
trap cleanup EXIT

cat > "${FAKE_BIN}/systemctl" <<'EOF'
#!/bin/sh
case "${1:-}" in
  is-active)
    exit 1
    ;;
  *)
    exit 0
    ;;
esac
EOF
chmod +x "${FAKE_BIN}/systemctl"

export PATH="${FAKE_BIN}:${PATH}"
export API_ID="12345"
export API_HASH="test-api-hash"
export BALE_BOT_TOKEN="test-bale-token"
export BALE_CHAT_ID="-10012345"
export SOURCE_CHANNELS="@example_one,@example_two"

bash "${ROOT_DIR}/setup.sh" \
  --non-interactive \
  --skip-auth \
  --skip-packages \
  --force-config

[[ -x /opt/telegram-to-bale/.venv/bin/python ]]
[[ -f /etc/systemd/system/tg2bale.service ]]
[[ -f /etc/telegram-to-bale.env ]]
[[ -d /var/lib/tg2bale ]]
id -u tg2bale >/dev/null

/opt/telegram-to-bale/.venv/bin/python \
  /opt/telegram-to-bale/main.py \
  --env-file /etc/telegram-to-bale.env \
  --check-config

/usr/local/bin/teltobale --version

if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze verify /etc/systemd/system/tg2bale.service
fi

bash /opt/telegram-to-bale/uninstall.sh --purge --yes
[[ ! -e /opt/telegram-to-bale ]]
[[ ! -e /etc/telegram-to-bale.env ]]
[[ ! -e /var/lib/tg2bale ]]

printf 'Installer integration test passed.\n'
