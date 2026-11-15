# Build static frontend ZIP for https://tiiny.host/manage (no Python API).
param(
  [Parameter(Mandatory = $false)]
  [string]$ApiUrl = '',
  [Parameter(Mandatory = $false)]
  [string]$OutZip = ''
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$fe = Join-Path $root 'frontend'
$dist = Join-Path $fe 'dist'
if (-not $OutZip) { $OutZip = Join-Path $root 'moloko-tiiny.zip' }

Push-Location $fe
$env:VITE_STATIC_HOST = 'tiiny'
if ($ApiUrl) {
  $env:VITE_API_URL = $ApiUrl.TrimEnd('/')
} else {
  Remove-Item Env:VITE_API_URL -ErrorAction SilentlyContinue
  Write-Host 'WARN: set -ApiUrl for working login. See docs/DEPLOY_TIINY.md' -ForegroundColor Yellow
}

npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }

Copy-Item (Join-Path $dist 'index.html') (Join-Path $dist '404.html') -Force
Pop-Location

if (Test-Path $OutZip) { Remove-Item $OutZip -Force }
Compress-Archive -Path (Join-Path $dist '*') -DestinationPath $OutZip -Force

$mb = [math]::Round((Get-Item $OutZip).Length / 1MB, 2)
Write-Host "OK: $OutZip ($mb MB)" -ForegroundColor Green
if ($mb -gt 3) {
  Write-Host 'WARN: free tiiny limit ~3 MB ZIP' -ForegroundColor Yellow
}
Write-Host 'Upload moloko-tiiny.zip at https://tiiny.host/manage'