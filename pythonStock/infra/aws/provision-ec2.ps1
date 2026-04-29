param(
  [string]$Region = "ap-northeast-2",
  [string]$ProjectName = "pythonstock",
  [string]$RepoUrl = "https://github.com/ehgus2390/pythonStock.git",
  [string]$Branch = "main",
  [string]$Ec2InstanceType = "t3.small",
  [string]$SecretName = "pythonstock/app",
  [string]$OpenAIApiKey = "",
  [string]$PremiumAccessCode = "",
  [string]$BillingEnabled = "false",
  [string]$FreeDailyAnalyses = "3",
  [string]$AnalysisCreditCost = "1",
  [string]$AiCreditCost = "2",
  [string]$AdminCreditCode = "",
  [string]$AdminCreditGrant = "20",
  [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"
$TempDir = Join-Path $env:TEMP "$ProjectName-provision"
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

function New-TempJsonFile([string]$Content, [string]$FileName) {
  $Path = Join-Path $TempDir $FileName
  Set-Content -LiteralPath $Path -Value $Content -Encoding ascii
  return $Path
}

function New-TempTextFile([string]$Content, [string]$FileName) {
  $Path = Join-Path $TempDir $FileName
  [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
  return $Path
}

function ConvertTo-DotEnvValue([string]$Value) {
  if ($null -eq $Value) {
    return '""'
  }

  $Escaped = $Value.Replace("\", "\\").Replace('"', '\"')
  return '"' + $Escaped + '"'
}

function Get-AppSecretText {
  param(
    [string]$EnvFilePath,
    [string]$OpenAI,
    [string]$Premium,
    [string]$Billing,
    [string]$FreeDaily,
    [string]$AnalysisCost,
    [string]$AiCost,
    [string]$AdminCode,
    [string]$AdminGrant
  )

  if (-not [string]::IsNullOrWhiteSpace($EnvFilePath) -and (Test-Path -LiteralPath $EnvFilePath)) {
    return Get-Content -LiteralPath $EnvFilePath -Raw
  }

  $DefaultEnvPath = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) ".env"
  if (Test-Path -LiteralPath $DefaultEnvPath) {
    return Get-Content -LiteralPath $DefaultEnvPath -Raw
  }

  return @"
OPENAI_API_KEY=$(ConvertTo-DotEnvValue $OpenAI)
PREMIUM_ACCESS_CODE=$(ConvertTo-DotEnvValue $Premium)
BILLING_ENABLED=$(ConvertTo-DotEnvValue $Billing)
FREE_DAILY_ANALYSES=$(ConvertTo-DotEnvValue $FreeDaily)
ANALYSIS_CREDIT_COST=$(ConvertTo-DotEnvValue $AnalysisCost)
AI_CREDIT_COST=$(ConvertTo-DotEnvValue $AiCost)
ADMIN_CREDIT_CODE=$(ConvertTo-DotEnvValue $AdminCode)
ADMIN_CREDIT_GRANT=$(ConvertTo-DotEnvValue $AdminGrant)
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
"@
}

function Wait-InstanceProfileReady {
  param([string]$InstanceProfileName)

  for ($i = 0; $i -lt 24; $i++) {
    $Profile = aws iam get-instance-profile --instance-profile-name $InstanceProfileName | ConvertFrom-Json
    if ($Profile.InstanceProfile.Roles.Count -gt 0) {
      Start-Sleep -Seconds 10
      return
    }
    Start-Sleep -Seconds 5
  }

  throw "Instance profile role attachment was not ready: $InstanceProfileName"
}

$CallerIdentity = aws sts get-caller-identity --region $Region | ConvertFrom-Json
$AccountId = $CallerIdentity.Account

$ProjectSlug = $ProjectName.ToLower()
$InstanceName = "$ProjectSlug-web"
$SecurityGroupName = "$ProjectSlug-ec2-sg"
$RoleName = "$ProjectSlug-ec2-ssm-role"
$InstanceProfileName = "$ProjectSlug-ec2-instance-profile"
$ElasticIpTagName = "$ProjectSlug-eip"

$Vpc = (aws ec2 describe-vpcs --region $Region --filters Name=is-default,Values=true | ConvertFrom-Json).Vpcs | Select-Object -First 1
if (-not $Vpc) {
  throw "No default VPC found in $Region."
}

$Subnets = (aws ec2 describe-subnets --region $Region --filters Name=vpc-id,Values=$($Vpc.VpcId) Name=default-for-az,Values=true | ConvertFrom-Json).Subnets
if (-not $Subnets) {
  throw "No default subnet found in $Region."
}

$SecurityGroup = (aws ec2 describe-security-groups --region $Region --filters Name=group-name,Values=$SecurityGroupName Name=vpc-id,Values=$($Vpc.VpcId) | ConvertFrom-Json).SecurityGroups | Select-Object -First 1
if (-not $SecurityGroup) {
  $SecurityGroupId = ((aws ec2 create-security-group --region $Region --group-name $SecurityGroupName --description "EC2 web access for $ProjectName" --vpc-id $($Vpc.VpcId)) | ConvertFrom-Json).GroupId
  aws ec2 create-tags --region $Region --resources $SecurityGroupId --tags Key=Name,Value=$SecurityGroupName Key=Project,Value=$ProjectSlug | Out-Null
  $SecurityGroup = (aws ec2 describe-security-groups --region $Region --group-ids $SecurityGroupId | ConvertFrom-Json).SecurityGroups[0]
}

$HasHttp = $SecurityGroup.IpPermissions | Where-Object { $_.FromPort -eq 80 -and $_.ToPort -eq 80 -and $_.IpProtocol -eq "tcp" }
if (-not $HasHttp) {
  aws ec2 authorize-security-group-ingress --region $Region --group-id $($SecurityGroup.GroupId) --protocol tcp --port 80 --cidr 0.0.0.0/0 | Out-Null
}

$HasHttps = $SecurityGroup.IpPermissions | Where-Object { $_.FromPort -eq 443 -and $_.ToPort -eq 443 -and $_.IpProtocol -eq "tcp" }
if (-not $HasHttps) {
  aws ec2 authorize-security-group-ingress --region $Region --group-id $($SecurityGroup.GroupId) --protocol tcp --port 443 --cidr 0.0.0.0/0 | Out-Null
}

$SecretText = Get-AppSecretText `
  -EnvFilePath $EnvFile `
  -OpenAI $OpenAIApiKey `
  -Premium $PremiumAccessCode `
  -Billing $BillingEnabled `
  -FreeDaily $FreeDailyAnalyses `
  -AnalysisCost $AnalysisCreditCost `
  -AiCost $AiCreditCost `
  -AdminCode $AdminCreditCode `
  -AdminGrant $AdminCreditGrant
$SecretTextPath = New-TempTextFile -Content $SecretText -FileName "app-secret.env"

$ExistingSecretJson = $null
try {
  $ExistingSecretJson = & aws secretsmanager describe-secret --secret-id $SecretName --region $Region 2>$null
} catch {
  $ExistingSecretJson = $null
}
if ($LASTEXITCODE -eq 0 -and $ExistingSecretJson) {
  aws secretsmanager update-secret --secret-id $SecretName --secret-string "file://$SecretTextPath" --region $Region | Out-Null
  $AppSecret = aws secretsmanager describe-secret --secret-id $SecretName --region $Region | ConvertFrom-Json
} else {
  $AppSecret = aws secretsmanager create-secret --name $SecretName --description "PythonStock app environment variables" --secret-string "file://$SecretTextPath" --region $Region | ConvertFrom-Json
}

$AssumeRolePolicy = @'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@
$AssumeRolePolicyPath = New-TempJsonFile -Content $AssumeRolePolicy -FileName "assume-role-policy.json"

$ExistingRoleArn = aws iam list-roles --query "Roles[?RoleName=='$RoleName'].Arn | [0]" --output text
if ($ExistingRoleArn -eq "None") {
  aws iam create-role --role-name $RoleName --assume-role-policy-document "file://$AssumeRolePolicyPath" | Out-Null
  aws iam attach-role-policy --role-name $RoleName --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore | Out-Null
}

$SecretReadPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "$($AppSecret.ARN)"
    }
  ]
}
"@
$SecretReadPolicyPath = New-TempJsonFile -Content $SecretReadPolicy -FileName "secret-read-policy.json"
aws iam put-role-policy --role-name $RoleName --policy-name "$ProjectSlug-secret-read" --policy-document "file://$SecretReadPolicyPath" | Out-Null

$ExistingInstanceProfileArn = aws iam list-instance-profiles --query "InstanceProfiles[?InstanceProfileName=='$InstanceProfileName'].Arn | [0]" --output text
if ($ExistingInstanceProfileArn -eq "None") {
  aws iam create-instance-profile --instance-profile-name $InstanceProfileName | Out-Null
}

$InstanceProfileRoleNames = aws iam list-instance-profiles --query "InstanceProfiles[?InstanceProfileName=='$InstanceProfileName'].Roles[].RoleName" --output text
if (-not $InstanceProfileRoleNames -or $InstanceProfileRoleNames -notmatch [regex]::Escape($RoleName)) {
  aws iam add-role-to-instance-profile --instance-profile-name $InstanceProfileName --role-name $RoleName | Out-Null
}
Wait-InstanceProfileReady -InstanceProfileName $InstanceProfileName

$AmiId = aws ssm get-parameter --region $Region --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64 --query Parameter.Value --output text

$BootstrapScript = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot "bootstrap-instance.sh")
$UserDataScript = @"
#!/bin/bash
cat <<'SCRIPT' >/tmp/pythonstock-bootstrap-instance.sh
$BootstrapScript
SCRIPT
chmod +x /tmp/pythonstock-bootstrap-instance.sh
/tmp/pythonstock-bootstrap-instance.sh "$RepoUrl" "$Branch" "$($AppSecret.ARN)" "$Region"
"@
$EncodedUserData = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($UserDataScript))

$Instance = (aws ec2 describe-instances --region $Region --filters Name=tag:Name,Values=$InstanceName Name=instance-state-name,Values=pending,running,stopping,stopped | ConvertFrom-Json).Reservations.Instances | Select-Object -First 1

if (-not $Instance) {
  $PrimarySubnet = ($Subnets | Sort-Object AvailabilityZone | Select-Object -First 1).SubnetId
  $RunResult = aws ec2 run-instances `
    --region $Region `
    --image-id $AmiId `
    --instance-type $Ec2InstanceType `
    --subnet-id $PrimarySubnet `
    --security-group-ids $($SecurityGroup.GroupId) `
    --iam-instance-profile Name=$InstanceProfileName `
    --user-data $EncodedUserData `
    --metadata-options HttpTokens=required,HttpEndpoint=enabled `
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$InstanceName},{Key=Project,Value=$ProjectSlug}]" | ConvertFrom-Json
  $Instance = $RunResult.Instances[0]
}

aws ec2 wait instance-running --region $Region --instance-ids $($Instance.InstanceId)
$Instance = (aws ec2 describe-instances --region $Region --instance-ids $($Instance.InstanceId) | ConvertFrom-Json).Reservations[0].Instances[0]

$ElasticIpAllocation = (aws ec2 describe-addresses --region $Region --filters Name=tag:Name,Values=$ElasticIpTagName | ConvertFrom-Json).Addresses | Select-Object -First 1
if (-not $ElasticIpAllocation) {
  $ElasticIpAllocation = aws ec2 allocate-address --region $Region --domain vpc | ConvertFrom-Json
  aws ec2 create-tags --region $Region --resources $ElasticIpAllocation.AllocationId --tags Key=Name,Value=$ElasticIpTagName Key=Project,Value=$ProjectSlug | Out-Null
}

if (-not $ElasticIpAllocation.AssociationId) {
  aws ec2 associate-address --region $Region --allocation-id $ElasticIpAllocation.AllocationId --instance-id $($Instance.InstanceId) | Out-Null
}

$ElasticIpAllocation = (aws ec2 describe-addresses --region $Region --allocation-ids $ElasticIpAllocation.AllocationId | ConvertFrom-Json).Addresses[0]

Write-Host ""
Write-Host "Provisioning summary"
Write-Host "Region: $Region"
Write-Host "AccountId: $AccountId"
Write-Host "VPC: $($Vpc.VpcId)"
Write-Host "EC2 InstanceId: $($Instance.InstanceId)"
Write-Host "EC2 Public IP: $($ElasticIpAllocation.PublicIp)"
Write-Host "Security Group: $($SecurityGroup.GroupId)"
Write-Host "Instance Profile: $InstanceProfileName"
Write-Host "App Secret Name: $SecretName"
Write-Host "App Secret ARN: $($AppSecret.ARN)"
Write-Host ""
Write-Host "DNS record:"
Write-Host "A  stock  $($ElasticIpAllocation.PublicIp)"
Write-Host ""
Write-Host "Deploy command:"
Write-Host ".\pythonStock\infra\aws\deploy-via-ssm.ps1 -InstanceId `"$($Instance.InstanceId)`" -Region `"$Region`" -AppSecretArn `"$($AppSecret.ARN)`""
