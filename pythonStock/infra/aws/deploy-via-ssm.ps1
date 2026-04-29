param(
  [string]$Region = "ap-northeast-2",
  [string]$InstanceName = "pythonstock-web",
  [string]$InstanceId = "",
  [string]$RepoUrl = "https://github.com/ehgus2390/pythonStock.git",
  [string]$Branch = "main",
  [string]$AppSecretArn = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InstanceId)) {
  $Instance = (aws ec2 describe-instances --region $Region --filters Name=tag:Name,Values=$InstanceName Name=instance-state-name,Values=running | ConvertFrom-Json).Reservations.Instances | Select-Object -First 1
  if (-not $Instance) {
    throw "Running EC2 instance not found. Pass -InstanceId or use tag Name=$InstanceName."
  }
  $InstanceId = $Instance.InstanceId
}

$Command = "/usr/local/bin/pythonstock-deploy.sh '$RepoUrl' '$Branch' '$AppSecretArn' '$Region'"
$ParametersJson = (@{
  commands = @($Command)
} | ConvertTo-Json -Compress)

$TempPath = Join-Path $env:TEMP "pythonstock-deploy-parameters.json"
Set-Content -LiteralPath $TempPath -Value $ParametersJson -Encoding ascii

aws ssm send-command `
  --region $Region `
  --instance-ids $InstanceId `
  --document-name "AWS-RunShellScript" `
  --comment "Deploy pythonstock" `
  --parameters "file://$TempPath"
