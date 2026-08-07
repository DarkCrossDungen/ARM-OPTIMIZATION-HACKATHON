# ArmDX security setup

ArmDX uses SSH local forwarding. The browser connects to `127.0.0.1:8000` on the laptop; SSH forwards that encrypted connection to `127.0.0.1:8000` on the VM. The VM service must never bind to a public interface.

## Current status

- Windows OpenSSH client: installed and verified.
- Local tunnel launcher: prepared in `scripts/start-ssh-tunnel.ps1`.
- Ed25519 key generator: prepared in `scripts/new-ssh-key.ps1`.
- VM SSH hardening: prepared in `scripts/harden-ubuntu-ssh.sh`.
- VM verification: prepared in `scripts/verify-remote-security.sh`.
- VM key, hostname, public IP restriction, and tunnel: pending because no VM exists.

## 1. Create a dedicated key on the laptop

Choose a private path outside the Git repository:

```powershell
.\scripts\new-ssh-key.ps1 -KeyPath "$env:USERPROFILE\.ssh\armdx_ed25519"
```

Add only the generated `.pub` file to the VM during provisioning. Never upload or commit the private key.

## 2. Restrict the cloud firewall

In the provider security list or network security group:

- allow inbound TCP port 22 only from your current public IP as a `/32` CIDR;
- remove any port 22 rule whose source is `0.0.0.0/0` or `::/0`;
- do not create an inbound rule for port 8000.

A changing residential public IP requires updating this rule before reconnecting.

## 3. Harden OpenSSH on the VM

Copy the scripts to the VM, keep the current SSH session open, and run:

```bash
sudo bash scripts/harden-ubuntu-ssh.sh YOUR_PUBLIC_IP ubuntu
```

The script refuses to disable password login unless `ubuntu` already has an authorized key. Open a second terminal and prove that key-only login works before closing the first session.

## 4. Bind ArmDX privately

On the VM:

```bash
.venv/bin/python -m uvicorn autopilot.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Verify the listener and SSH policy:

```bash
sudo bash scripts/verify-remote-security.sh
```

The listener must show `127.0.0.1:8000`, never `0.0.0.0:8000` or `[::]:8000`.

## 5. Start the encrypted tunnel

On the laptop:

```powershell
.\scripts\start-ssh-tunnel.ps1 -VmHost VM_PUBLIC_IP -KeyPath "$env:USERPROFILE\.ssh\armdx_ed25519"
```

Keep that terminal open and browse to `http://127.0.0.1:8000`.

## Security boundary

The tunnel provides encryption and server authentication. It does not compensate for a leaked private key, an unrestricted cloud firewall, a compromised laptop or VM, or unsafe application code. Apply OS updates, protect the private key, and rotate the key if exposure is suspected.
