# test_local_proxy.ps1 — Verify the CLIProxyAPI local proxy is reachable
# Convenience script only — not part of the application runtime.

$BaseUrl = "http://127.0.0.1:8317/v1"

Write-Host "Testing local proxy at $BaseUrl ..." -ForegroundColor Cyan

# Check if proxy is reachable
try {
    $models = Invoke-RestMethod -Uri "$BaseUrl/models" -Method GET -TimeoutSec 5
    Write-Host "Proxy is reachable." -ForegroundColor Green
    Write-Host ""
    Write-Host "Available models:" -ForegroundColor Yellow
    foreach ($model in $models.data) {
        Write-Host "  - $($model.id)"
    }
} catch {
    Write-Error "Cannot reach proxy at $BaseUrl"
    Write-Error "Make sure cli-proxy-api.exe is running. See docs/local_claude_proxy_setup.md"
    Write-Error "Error: $_"
    exit 1
}
