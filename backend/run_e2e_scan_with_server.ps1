param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [int]$StartupTimeoutSec = 30
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $scriptDir "..\.venv\Scripts\python.exe"
$apiUrl = "http://$BindHost`:$Port/docs"
$uvicornProcess = $null

function Wait-ForApi {
    param(
        [string]$Url,
        [int]$TimeoutSec
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    return $false
}

try {
    Write-Host "[e2e] Starting backend on ${BindHost}:$Port ..."
    $uvicornProcess = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "main:app", "--host", $BindHost, "--port", $Port) -WorkingDirectory $scriptDir -PassThru

    if (-not (Wait-ForApi -Url $apiUrl -TimeoutSec $StartupTimeoutSec)) {
        throw "Backend did not become healthy within $StartupTimeoutSec seconds."
    }

    Write-Host "[e2e] Backend is up. Running test_e2e_scan.py ..."
    & $pythonExe (Join-Path $scriptDir "test_e2e_scan.py")
    if ($LASTEXITCODE -ne 0) {
        throw "E2E test failed with exit code $LASTEXITCODE"
    }

    Write-Host "[e2e] E2E verification passed."
}
finally {
    if ($uvicornProcess -and -not $uvicornProcess.HasExited) {
        Write-Host "[e2e] Stopping backend process $($uvicornProcess.Id) ..."
        Stop-Process -Id $uvicornProcess.Id -Force
    }
}
