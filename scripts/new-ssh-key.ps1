[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$KeyPath,
    [string]$Comment = "armdx-operator"
)

$ErrorActionPreference = "Stop"
$sshKeygen = Get-Command ssh-keygen.exe -ErrorAction Stop
$expandedPath = [Environment]::ExpandEnvironmentVariables($KeyPath)
$parent = Split-Path -Parent $expandedPath
if (-not $parent) { throw "KeyPath must include a parent directory." }
if (Test-Path -LiteralPath $expandedPath) { throw "Refusing to overwrite existing key: $expandedPath" }
New-Item -ItemType Directory -Force -Path $parent | Out-Null
& $sshKeygen.Source -t ed25519 -a 64 -f $expandedPath -C $Comment
if ($LASTEXITCODE -ne 0) { throw "ssh-keygen exited with code $LASTEXITCODE" }
Write-Host "Private key: $expandedPath"
Write-Host "Public key:  $expandedPath.pub"
Write-Host "Keep the private key private; add only the .pub key to the VM."
