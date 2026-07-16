# 관리자 권한 PowerShell에서 실행하세요.
$ErrorActionPreference = "Stop"

$ServiceName = "IndustrialAI-Dashboard"
$Nssm = Join-Path $PSScriptRoot "nssm.exe"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "이 스크립트는 관리자 권한 PowerShell에서 실행해야 합니다."
    exit 1
}

& $Nssm stop $ServiceName confirm
& $Nssm remove $ServiceName confirm
Remove-NetFirewallRule -DisplayName "Streamlit-8501" -ErrorAction SilentlyContinue
Write-Host "서비스 제거 완료."
