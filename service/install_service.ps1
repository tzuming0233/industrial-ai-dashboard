# 관리자 권한 PowerShell에서 실행하세요.
# 우클릭 -> "관리자 권한으로 PowerShell 실행" 후 이 스크립트를 실행합니다:
#   cd 이 폴더 경로로 이동 후 -> .\install_service.ps1

$ErrorActionPreference = "Stop"

$ServiceName = "IndustrialAI-Dashboard"
$ProjectDir  = (Resolve-Path "$PSScriptRoot\..").Path
$StreamlitExe = Join-Path $ProjectDir "myenv\Scripts\streamlit.exe"
$Nssm = Join-Path $PSScriptRoot "nssm.exe"
$LogDir = Join-Path $PSScriptRoot "logs"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "이 스크립트는 관리자 권한 PowerShell에서 실행해야 합니다."
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# 이미 등록된 서비스가 있으면 제거 후 재등록 (재실행 시 안전하게 갱신)
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    & $Nssm stop $ServiceName confirm
    & $Nssm remove $ServiceName confirm
}

& $Nssm install $ServiceName $StreamlitExe "run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true"
& $Nssm set $ServiceName AppDirectory $ProjectDir
& $Nssm set $ServiceName DisplayName "산업AI팀 사업 통합관리 (Streamlit)"
& $Nssm set $ServiceName Start SERVICE_AUTO_START
& $Nssm set $ServiceName AppStdout (Join-Path $LogDir "stdout.log")
& $Nssm set $ServiceName AppStderr (Join-Path $LogDir "stderr.log")
& $Nssm set $ServiceName AppRotateFiles 1
& $Nssm set $ServiceName AppRotateBytes 10485760
& $Nssm set $ServiceName AppRestartDelay 5000

# 사내망에서 접속할 수 있도록 방화벽 인바운드 규칙 추가 (이미 있으면 건너뜀)
if (-not (Get-NetFirewallRule -DisplayName "Streamlit-8501" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Streamlit-8501" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow | Out-Null
}

Start-Service -Name $ServiceName
Start-Sleep -Seconds 3
Get-Service -Name $ServiceName | Format-List Name, Status, StartType

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.IPAddress -notlike "169.*" } | Select-Object -First 1 -ExpandProperty IPAddress)
Write-Host ""
Write-Host "서비스 등록 완료. 접속 주소:"
Write-Host "  이 PC에서: http://localhost:8501"
Write-Host "  같은 네트워크의 팀원: http://$ip:8501"
Write-Host ""
Write-Host "주의: .env 파일에 ANTHROPIC_API_KEY를 채워 넣지 않으면 AI 질의 탭은 동작하지 않습니다."
