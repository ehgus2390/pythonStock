param(
  [string]$Region = "ap-northeast-2",
  [string]$SecretName = "pythonstock/app",
  [string]$EnvFile = "",
  [string]$OpenAIApiKey = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($EnvFile)) {
  $EnvFile = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) ".env"
}

if (Test-Path -LiteralPath $EnvFile) {
  $SecretText = Get-Content -LiteralPath $EnvFile -Raw
} else {
  if ([string]::IsNullOrWhiteSpace($OpenAIApiKey)) {
    throw "No .env file found at '$EnvFile'. Pass -OpenAIApiKey, or create pythonStock\.env first."
  }

  $SecretText = @"
OPENAI_API_KEY=$OpenAIApiKey
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
"@
}

$TempPath = Join-Path $env:TEMP "pythonstock-app-secret.env"

try {
  [System.IO.File]::WriteAllText($TempPath, $SecretText, [System.Text.UTF8Encoding]::new($false))

  $ExistingSecret = $null
  try {
    $ExistingSecretJson = & aws secretsmanager describe-secret `
      --region $Region `
      --secret-id $SecretName 2>$null
    if ($LASTEXITCODE -eq 0 -and $ExistingSecretJson) {
      $ExistingSecret = $ExistingSecretJson | ConvertFrom-Json
    }
  } catch {
    $ExistingSecret = $null
  }

  if ($ExistingSecret) {
    $Result = aws secretsmanager update-secret `
      --region $Region `
      --secret-id $SecretName `
      --secret-string "file://$TempPath" | ConvertFrom-Json
  } else {
    $Result = aws secretsmanager create-secret `
      --region $Region `
      --name $SecretName `
      --description "PythonStock web app environment variables" `
      --secret-string "file://$TempPath" | ConvertFrom-Json
  }

  Write-Host "Secret synced."
  Write-Host "Secret ARN: $($Result.ARN)"
  Write-Host ""
  Write-Host "Use this ARN with bootstrap/deploy:"
  Write-Host "-AppSecretArn `"$($Result.ARN)`""
} finally {
  if (Test-Path -LiteralPath $TempPath) {
    Remove-Item -LiteralPath $TempPath -Force
  }
}
