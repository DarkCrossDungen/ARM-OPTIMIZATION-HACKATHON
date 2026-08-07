#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo $0 [project-directory] [service-user]" >&2
  exit 1
fi

PROJECT_DIR="${1:-/opt/armdx}"
SERVICE_USER="${2:-ubuntu}"
if [[ ! -f "$PROJECT_DIR/deploy/armdx.service" ]]; then
  echo "ArmDX service file not found in $PROJECT_DIR" >&2
  exit 1
fi
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "Service user does not exist: $SERVICE_USER" >&2
  exit 1
fi

sed "s|^User=ubuntu$|User=$SERVICE_USER|;s|^WorkingDirectory=/opt/armdx$|WorkingDirectory=$PROJECT_DIR|;s|/opt/armdx|$PROJECT_DIR|g" "$PROJECT_DIR/deploy/armdx.service" >/etc/systemd/system/armdx.service
systemctl daemon-reload
systemctl enable --now armdx.service
systemctl --no-pager --full status armdx.service
