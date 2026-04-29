# PythonStock EC2 Website Deployment

This deployment path mirrors the `Dashboard` project style:

- EC2 runs the app with PM2.
- AWS SSM sends bootstrap/deploy commands from local PowerShell.
- Nginx exposes the app as a normal website on `80/443`.
- Streamlit runs privately on `127.0.0.1:8501`.

## Prerequisites

- EC2 instance running Amazon Linux 2023.
- EC2 IAM role with `AmazonSSMManagedInstanceCore`.
- If using AWS Secrets Manager, the EC2 role also needs `secretsmanager:GetSecretValue` for the app secret.
- Security group inbound: `80`, `443`; `22` is optional if you use SSM only.
- AWS CLI configured locally.
- DNS `A` record pointing the domain to the EC2 public IP or Elastic IP.

## 1. Sync App Secret

Do not commit `.env` to GitHub. Create or update the AWS Secrets Manager secret from PowerShell:

```powershell
cd C:\Users\ad\Documents\GitHub\pythonStock
.\pythonStock\infra\aws\sync-app-secret.ps1 `
  -Region "ap-northeast-2" `
  -SecretName "pythonstock/app" `
  -OpenAIApiKey "sk-..." `
  -PremiumAccessCode "your-premium-code"
```

If `pythonStock\.env` already exists locally, the script reads it automatically:

```powershell
.\pythonStock\infra\aws\sync-app-secret.ps1 `
  -Region "ap-northeast-2" `
  -SecretName "pythonstock/app"
```

The script prints the `Secret ARN`. Use it as `-AppSecretArn` in bootstrap/deploy commands.

## 2. Bootstrap EC2

```powershell
cd C:\Users\ad\Documents\GitHub\pythonStock
.\pythonStock\infra\aws\bootstrap-via-ssm.ps1 `
  -InstanceId "i-xxxxxxxxxxxxxxxxx" `
  -Region "ap-northeast-2" `
  -AppSecretArn "arn:aws:secretsmanager:ap-northeast-2:123456789012:secret:pythonstock/app"
```

The secret may be either `.env` text or JSON such as:

```json
{
  "OPENAI_API_KEY": "sk-...",
  "PREMIUM_ACCESS_CODE": "your-code",
  "STREAMLIT_SERVER_HEADLESS": "true",
  "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"
}
```

## 3. Deploy Updates

After pushing code to GitHub:

```powershell
.\pythonStock\infra\aws\deploy-via-ssm.ps1 `
  -InstanceId "i-xxxxxxxxxxxxxxxxx" `
  -Region "ap-northeast-2" `
  -AppSecretArn "arn:aws:secretsmanager:ap-northeast-2:123456789012:secret:pythonstock/app"
```

Or find the instance by tag:

```powershell
.\pythonStock\infra\aws\deploy-via-ssm.ps1 `
  -InstanceName "pythonstock-web" `
  -Region "ap-northeast-2"
```

## 4. Configure HTTPS

Run this after the DNS record points to EC2:

```powershell
.\pythonStock\infra\aws\setup-ssl-via-ssm.ps1 `
  -InstanceId "i-xxxxxxxxxxxxxxxxx" `
  -DomainName "stock.nested.cyou" `
  -Email "you@example.com" `
  -Region "ap-northeast-2"
```

## 5. Check App Logs

From an SSM shell or SSH:

```bash
sudo systemctl status pm2-ec2-user
sudo -u ec2-user PM2_HOME=/home/ec2-user/.pm2 pm2 status
sudo -u ec2-user PM2_HOME=/home/ec2-user/.pm2 pm2 logs pythonstock
sudo nginx -t
```

Restart only the app:

```bash
sudo -u ec2-user PM2_HOME=/home/ec2-user/.pm2 pm2 restart pythonstock --update-env
```

## 6. Streamlit Cloud

After EC2 is serving the site, stop or delete the Streamlit Cloud app from the Streamlit Cloud dashboard. The EC2 deployment does not depend on Streamlit Cloud.
