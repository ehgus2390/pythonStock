# EC2 Deployment Guide

This guide runs the existing Streamlit app as a public website on EC2 behind Nginx.

## 1. EC2 Baseline

Recommended starter instance:

- Ubuntu 22.04 or 24.04 LTS
- t3.small or larger
- Security group inbound: `22`, `80`, `443`

## 2. Install Packages

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git nginx
```

## 3. Clone And Install

```bash
cd /home/ubuntu
git clone https://github.com/ehgus2390/pythonStock.git
cd /home/ubuntu/pythonStock/pythonStock
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Environment Variables

```bash
cp .env.example .env
nano .env
```

Set `OPENAI_API_KEY` only if AI summaries should be enabled.

## 5. Test Manually

```bash
cd /home/ubuntu/pythonStock/pythonStock
source .venv/bin/activate
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Stop with `Ctrl+C` after testing.

## 6. Install Systemd Service

```bash
sudo cp /home/ubuntu/pythonStock/pythonStock/deploy/ec2/stock-web.service /etc/systemd/system/stock-web.service
sudo systemctl daemon-reload
sudo systemctl enable stock-web
sudo systemctl start stock-web
sudo systemctl status stock-web
```

Logs:

```bash
journalctl -u stock-web -f
```

## 7. Configure Nginx

Edit the domain in `deploy/ec2/nginx-pythonstock.conf`, then run:

```bash
sudo cp /home/ubuntu/pythonStock/pythonStock/deploy/ec2/nginx-pythonstock.conf /etc/nginx/sites-available/pythonstock
sudo ln -s /etc/nginx/sites-available/pythonstock /etc/nginx/sites-enabled/pythonstock
sudo nginx -t
sudo systemctl reload nginx
```

## 8. HTTPS

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## 9. Update Deployment

```bash
cd /home/ubuntu/pythonStock
git pull
cd /home/ubuntu/pythonStock/pythonStock
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart stock-web
```

## Notes For Monetization

- Keep the app positioned as an analysis tool, not personalized investment advice.
- Use clear wording: data analysis, risk indicators, scenario estimates.
- Avoid direct commands such as "buy now" or "sell now".
- Add a visible disclaimer before adding payment.
