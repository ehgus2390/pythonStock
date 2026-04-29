param(
  [string]$Region = "ap-northeast-2",
  [Parameter(Mandatory = $true)]
  [string]$InstanceId,
  [Parameter(Mandatory = $true)]
  [string]$DomainName,
  [string]$Email = "",
  [switch]$NoEmail
)

$ErrorActionPreference = "Stop"

$EmailArguments = if ($NoEmail -or [string]::IsNullOrWhiteSpace($Email)) {
  "--register-unsafely-without-email"
} else {
  "--email '$Email'"
}

$Commands = @(
  "set -euo pipefail",
  "dnf install -y certbot python3-certbot-nginx",
  "cat >/etc/nginx/conf.d/pythonstock.conf <<'EOF'",
  "server {",
  "  listen 80;",
  "  server_name $DomainName;",
  "",
  "  client_max_body_size 10m;",
  "",
  "  location / {",
  "    proxy_pass http://127.0.0.1:8501;",
  "    proxy_http_version 1.1;",
  "    proxy_set_header Host `$host;",
  "    proxy_set_header X-Real-IP `$remote_addr;",
  "    proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;",
  "    proxy_set_header X-Forwarded-Proto `$scheme;",
  "    proxy_set_header Upgrade `$http_upgrade;",
  "    proxy_set_header Connection ""upgrade"";",
  "    proxy_cache_bypass `$http_upgrade;",
  "    proxy_read_timeout 86400;",
  "  }",
  "}",
  "EOF",
  "nginx -t",
  "systemctl restart nginx",
  "certbot --nginx --non-interactive --agree-tos $EmailArguments --redirect -d '$DomainName'",
  "systemctl reload nginx",
  "systemctl enable --now certbot-renew.timer",
  "certbot renew --dry-run"
)

$ParametersJson = (@{
  commands = $Commands
} | ConvertTo-Json -Compress -Depth 4)

$TempPath = Join-Path $env:TEMP "pythonstock-ssl-parameters.json"
Set-Content -LiteralPath $TempPath -Value $ParametersJson -Encoding ascii

aws ssm send-command `
  --region $Region `
  --instance-ids $InstanceId `
  --document-name "AWS-RunShellScript" `
  --comment "Setup HTTPS for pythonstock" `
  --parameters "file://$TempPath"
