param(
  [string]$Region = "ap-northeast-2",
  [Parameter(Mandatory = $true)]
  [string]$InstanceId,
  [string]$RepoUrl = "https://github.com/ehgus2390/pythonStock.git",
  [string]$Branch = "main",
  [string]$AppSecretArn = ""
)

$ErrorActionPreference = "Stop"

$BootstrapScript = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot "bootstrap-instance.sh"))
$Commands = @(
  "cat <<'SCRIPT' >/tmp/pythonstock-bootstrap-instance.sh",
  $BootstrapScript,
  "SCRIPT",
  "chmod +x /tmp/pythonstock-bootstrap-instance.sh",
  "/tmp/pythonstock-bootstrap-instance.sh '$RepoUrl' '$Branch' '$AppSecretArn' '$Region'"
)

$ParametersJson = (@{
  commands = $Commands
} | ConvertTo-Json -Compress -Depth 4)

$TempPath = Join-Path $env:TEMP "pythonstock-bootstrap-parameters.json"
Set-Content -LiteralPath $TempPath -Value $ParametersJson -Encoding ascii

aws ssm send-command `
  --region $Region `
  --instance-ids $InstanceId `
  --document-name "AWS-RunShellScript" `
  --comment "Bootstrap pythonstock" `
  --parameters "file://$TempPath"
