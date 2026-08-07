[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$VmHost,
    [Parameter(Mandatory = $true)][string]$KeyPath,
    [string]$VmUser = "ubuntu",
    [ValidateRange(1024, 65535)][int]$LocalPort = 8000,
    [ValidateRange(1, 65535)][int]$RemotePort = 8000
)

$ErrorActionPreference = "Stop"
$ssh = Get-Command ssh.exe -ErrorAction Stop
$resolvedKey = (Resolve-Path -LiteralPath $KeyPath).Path

$arguments = @(
    "-N",
    "-L", "127.0.0.1:${LocalPort}:127.0.0.1:${RemotePort}",
    "-i", $resolvedKey,
    "-o", "BatchMode=yes",
    "-o", "PasswordAuthentication=no",
    "-o", "KbdInteractiveAuthentication=no",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3",
    "-o", "StrictHostKeyChecking=accept-new",
    "${VmUser}@${VmHost}"
)

Write-Host "Opening encrypted local tunnel on http://127.0.0.1:$LocalPort"
Write-Host "The dashboard is not exposed on a public web port. Keep this window open."
& $ssh.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "SSH tunnel exited with code $LASTEXITCODE" }
