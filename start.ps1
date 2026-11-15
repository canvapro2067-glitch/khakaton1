$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$env:PYTHONPATH = $root
Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","backend.app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $root
Set-Location "$root\frontend"
npm run dev
