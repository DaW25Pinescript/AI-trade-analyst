# start_local_proxy.ps1 — Start the CLIProxyAPI local proxy
# Convenience script only — not part of the application runtime.

$ProxyPath = "C:\cliproxyapi\cli-proxy-api.exe"

if (-not (Test-Path $ProxyPath)) {
    Write-Error "CLIProxyAPI not found at $ProxyPath"
    Write-Error "Download cli-proxy-api.exe and place it in C:\cliproxyapi\"
    exit 1
}

Write-Host "Starting CLIProxyAPI local proxy..." -ForegroundColor Green
Write-Host "Endpoint: http://127.0.0.1:8317/v1" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

& $ProxyPath
