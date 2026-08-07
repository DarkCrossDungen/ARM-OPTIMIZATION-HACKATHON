#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo $0 <allowed-public-ip> [ssh-user]" >&2
  exit 1
fi
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: sudo $0 <allowed-public-ip> [ssh-user]" >&2
  exit 1
fi

ALLOWED_IP="$1"
SSH_USER="${2:-ubuntu}"
if ! [[ "$ALLOWED_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "Provide one IPv4 address without /0; example: 203.0.113.10" >&2
  exit 1
fi
if ! id "$SSH_USER" >/dev/null 2>&1; then
  echo "SSH user does not exist: $SSH_USER" >&2
  exit 1
fi
if [[ ! -s "/home/$SSH_USER/.ssh/authorized_keys" ]]; then
  echo "Refusing to disable passwords before $SSH_USER has an authorized key." >&2
  exit 1
fi

install -d -m 0755 /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/99-armdx-hardening.conf <<EOF
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
AllowUsers $SSH_USER
AllowTcpForwarding local
GatewayPorts no
X11Forwarding no
PermitTunnel no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 120
ClientAliveCountMax 2
EOF

sshd -t
systemctl reload ssh

if command -v ufw >/dev/null 2>&1; then
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow from "$ALLOWED_IP" to any port 22 proto tcp comment 'ArmDX operator SSH'
  ufw --force enable
fi

echo "OpenSSH hardened. Keep the current SSH session open and verify a second key-only login before disconnecting."
echo "Also restrict the cloud security-list port 22 rule to ${ALLOWED_IP}/32 and do not open port 8000."
