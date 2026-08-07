#!/usr/bin/env bash
set -euo pipefail

echo "Effective SSH controls"
sshd -T | grep -E '^(passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|permitrootlogin|allowtcpforwarding|gatewayports|x11forwarding|permitunnel|maxauthtries) '

echo
echo "Dashboard listeners"
ss -ltnp | grep ':8000' || true

echo
echo "Expected: 127.0.0.1:8000 only; 0.0.0.0:8000 or [::]:8000 is unsafe."
if command -v ufw >/dev/null 2>&1; then
  echo
echo "Host firewall"
  ufw status verbose
fi
