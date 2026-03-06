# test_local_proxy_chat.ps1 — Send a test chat completion to the local proxy
# Convenience script only — not part of the application runtime.

$BaseUrl = "http://127.0.0.1:8317/v1"

# Optionally read model from config/llm_routing.yaml if available
$DefaultModel = "claude-sonnet-4-5-20250929"
$ConfigPath = Join-Path $PSScriptRoot "..\config\llm_routing.yaml"
if (Test-Path $ConfigPath) {
    $configContent = Get-Content $ConfigPath -Raw
    # Simple regex to extract a model name from the YAML
    if ($configContent -match 'primary_model:\s*"([^"]+)"') {
        $DefaultModel = $Matches[1]
        Write-Host "Using model from config: $DefaultModel" -ForegroundColor Cyan
    }
}

$body = @{
    model = $DefaultModel
    messages = @(
        @{ role = "user"; content = "Say hello in exactly one sentence." }
    )
    max_tokens = 100
} | ConvertTo-Json -Depth 4

Write-Host "Sending chat completion to $BaseUrl/chat/completions ..." -ForegroundColor Cyan
Write-Host "Model: $DefaultModel" -ForegroundColor Cyan
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/chat/completions" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -TimeoutSec 30

    $reply = $response.choices[0].message.content
    Write-Host "Response:" -ForegroundColor Green
    Write-Host $reply
    Write-Host ""
    Write-Host "Chat completion test passed." -ForegroundColor Green
} catch {
    Write-Error "Chat completion failed."
    Write-Error "Make sure cli-proxy-api.exe is running. See docs/local_claude_proxy_setup.md"
    Write-Error "Error: $_"
    exit 1
}
