#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/srv/pythonstock"
APP_DIR="${APP_ROOT}/app"
DEPLOY_DIR="${APP_ROOT}/deploy"
APP_USER="ec2-user"
APP_HOME="/home/${APP_USER}"
PM2_HOME_DIR="${APP_HOME}/.pm2"
REPO_URL="${1:-https://github.com/ehgus2390/pythonStock.git}"
BRANCH="${2:-main}"
APP_ENV_SECRET_ARN="${3:-}"
AWS_REGION="${4:-ap-northeast-2}"

sync_source() {
  local source_location="$1"
  local branch="$2"
  local app_dir="$3"

  if [[ "${source_location}" == s3://* ]]; then
    rm -rf "${app_dir}"
    mkdir -p "${app_dir}"
    aws s3 cp "${source_location}" /tmp/pythonstock.tar.gz --region "${AWS_REGION}"
    tar -xzf /tmp/pythonstock.tar.gz -C "${app_dir}" --strip-components=1
    chown -R "${APP_USER}:${APP_USER}" "${app_dir}"
    return
  fi

  if [ ! -d "${app_dir}/.git" ]; then
    rm -rf "${app_dir}"
    sudo -u "${APP_USER}" git clone --branch "${branch}" "${source_location}" "${app_dir}"
  else
    sudo -u "${APP_USER}" bash -lc "cd '${app_dir}' && git fetch origin && git reset --hard origin/${branch}"
  fi
}

run_as_app_user() {
  local command="$1"
  sudo -u "${APP_USER}" env \
    HOME="${APP_HOME}" \
    PM2_HOME="${PM2_HOME_DIR}" \
    PATH="/usr/local/bin:/usr/bin:/bin:${APP_DIR}/pythonStock/.venv/bin" \
    bash -lc "${command}"
}

write_env_from_secret() {
  local secret_arn="$1"
  local region="$2"
  local env_path="${APP_DIR}/pythonStock/.env"

  if [ -z "${secret_arn}" ]; then
    if [ ! -f "${env_path}" ] && [ -f "${APP_DIR}/pythonStock/.env.example" ]; then
      cp "${APP_DIR}/pythonStock/.env.example" "${env_path}"
    fi
    chown "${APP_USER}:${APP_USER}" "${env_path}" 2>/dev/null || true
    chmod 600 "${env_path}" 2>/dev/null || true
    return
  fi

  local secret_string
  secret_string="$(aws secretsmanager get-secret-value \
    --secret-id "${secret_arn}" \
    --region "${region}" \
    --query SecretString \
    --output text)"

  if echo "${secret_string}" | jq -e 'type == "object"' >/dev/null 2>&1; then
    echo "${secret_string}" | jq -r 'to_entries[] | "\(.key)=\(.value)"' > "${env_path}"
  else
    printf "%s\n" "${secret_string}" > "${env_path}"
  fi

  chown "${APP_USER}:${APP_USER}" "${env_path}"
  chmod 600 "${env_path}"
}

install_python_deps() {
  run_as_app_user "cd '${APP_DIR}/pythonStock' && python3.11 -m venv .venv"
  run_as_app_user "cd '${APP_DIR}/pythonStock' && .venv/bin/python -m pip install --upgrade pip"
  run_as_app_user "cd '${APP_DIR}/pythonStock' && .venv/bin/pip install -r requirements.txt"
}

write_nginx_config() {
  if [ -f "${APP_DIR}/pythonStock/infra/aws/nginx-pythonstock.conf" ]; then
    cp "${APP_DIR}/pythonStock/infra/aws/nginx-pythonstock.conf" /etc/nginx/conf.d/pythonstock.conf
  else
    cat >/etc/nginx/conf.d/pythonstock.conf <<'EOF'
server {
  listen 80;
  server_name _;

  client_max_body_size 10m;

  location / {
    proxy_pass http://127.0.0.1:8501;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_cache_bypass $http_upgrade;
    proxy_read_timeout 86400;
  }
}
EOF
  fi

  nginx -t
  systemctl enable nginx
}

install_pm2_systemd_service() {
  local pm2_bin
  pm2_bin="$(command -v pm2)"

  cat >/etc/systemd/system/pm2-ec2-user.service <<EOF
[Unit]
Description=PM2 process manager for PythonStock
Documentation=https://pm2.keymetrics.io/
After=network.target

[Service]
Type=forking
User=${APP_USER}
LimitNOFILE=infinity
LimitNPROC=infinity
LimitCORE=infinity
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=PM2_HOME=${PM2_HOME_DIR}
Environment=HOME=${APP_HOME}
PIDFile=${PM2_HOME_DIR}/pm2.pid
Restart=on-failure

ExecStart=${pm2_bin} resurrect
ExecReload=${pm2_bin} reload all
ExecStop=${pm2_bin} kill

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable pm2-ec2-user
}

copy_pm2_config() {
  mkdir -p "${DEPLOY_DIR}"
  if [ -f "${APP_DIR}/pythonStock/infra/aws/ecosystem.config.cjs" ]; then
    cp "${APP_DIR}/pythonStock/infra/aws/ecosystem.config.cjs" "${DEPLOY_DIR}/ecosystem.config.cjs"
  else
    cat >"${DEPLOY_DIR}/ecosystem.config.cjs" <<'EOF'
module.exports = {
  apps: [
    {
      name: "pythonstock",
      cwd: "/srv/pythonstock/app/pythonStock",
      script: "/usr/bin/bash",
      args: [
        "-lc",
        "set -a; [ -f .env ] && . ./.env; set +a; exec .venv/bin/streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true",
      ],
      interpreter: "none",
      env: {
        STREAMLIT_SERVER_HEADLESS: "true",
        STREAMLIT_BROWSER_GATHER_USAGE_STATS: "false",
      },
      max_restarts: 10,
      restart_delay: 5000,
    },
  ],
};
EOF
  fi
  chown -R "${APP_USER}:${APP_USER}" "${DEPLOY_DIR}"
}

start_pm2_app() {
  run_as_app_user "pm2 startOrReload '${DEPLOY_DIR}/ecosystem.config.cjs' --update-env"
  run_as_app_user "pm2 save"
  install_pm2_systemd_service
  systemctl restart pm2-ec2-user
}

write_deploy_script() {
  cat >/usr/local/bin/pythonstock-deploy.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/srv/pythonstock"
APP_DIR="${APP_ROOT}/app"
DEPLOY_DIR="${APP_ROOT}/deploy"
APP_USER="ec2-user"
APP_HOME="/home/${APP_USER}"
PM2_HOME_DIR="${APP_HOME}/.pm2"
REPO_URL="${1:-https://github.com/ehgus2390/pythonStock.git}"
BRANCH="${2:-main}"
APP_ENV_SECRET_ARN="${3:-}"
AWS_REGION="${4:-ap-northeast-2}"

sync_source() {
  local source_location="$1"
  local branch="$2"
  local app_dir="$3"

  if [[ "${source_location}" == s3://* ]]; then
    rm -rf "${app_dir}"
    mkdir -p "${app_dir}"
    aws s3 cp "${source_location}" /tmp/pythonstock.tar.gz --region "${AWS_REGION}"
    tar -xzf /tmp/pythonstock.tar.gz -C "${app_dir}" --strip-components=1
    chown -R "${APP_USER}:${APP_USER}" "${app_dir}"
    return
  fi

  if [ ! -d "${app_dir}/.git" ]; then
    rm -rf "${app_dir}"
    sudo -u "${APP_USER}" git clone --branch "${branch}" "${source_location}" "${app_dir}"
  else
    sudo -u "${APP_USER}" bash -lc "cd '${app_dir}' && git fetch origin && git reset --hard origin/${branch}"
  fi
}

run_as_app_user() {
  local command="$1"
  sudo -u "${APP_USER}" env \
    HOME="${APP_HOME}" \
    PM2_HOME="${PM2_HOME_DIR}" \
    PATH="/usr/local/bin:/usr/bin:/bin:${APP_DIR}/pythonStock/.venv/bin" \
    bash -lc "${command}"
}

write_env_from_secret() {
  local secret_arn="$1"
  local region="$2"
  local env_path="${APP_DIR}/pythonStock/.env"

  if [ -z "${secret_arn}" ]; then
    if [ ! -f "${env_path}" ] && [ -f "${APP_DIR}/pythonStock/.env.example" ]; then
      cp "${APP_DIR}/pythonStock/.env.example" "${env_path}"
    fi
    chown "${APP_USER}:${APP_USER}" "${env_path}" 2>/dev/null || true
    chmod 600 "${env_path}" 2>/dev/null || true
    return
  fi

  local secret_string
  secret_string="$(aws secretsmanager get-secret-value \
    --secret-id "${secret_arn}" \
    --region "${region}" \
    --query SecretString \
    --output text)"

  if echo "${secret_string}" | jq -e 'type == "object"' >/dev/null 2>&1; then
    echo "${secret_string}" | jq -r 'to_entries[] | "\(.key)=\(.value)"' > "${env_path}"
  else
    printf "%s\n" "${secret_string}" > "${env_path}"
  fi

  chown "${APP_USER}:${APP_USER}" "${env_path}"
  chmod 600 "${env_path}"
}

sync_source "${REPO_URL}" "${BRANCH}" "${APP_DIR}"
write_env_from_secret "${APP_ENV_SECRET_ARN}" "${AWS_REGION}"

sudo -u "${APP_USER}" bash -lc "cd '${APP_DIR}/pythonStock' && python3.11 -m venv .venv"
run_as_app_user "cd '${APP_DIR}/pythonStock' && .venv/bin/python -m pip install --upgrade pip"
run_as_app_user "cd '${APP_DIR}/pythonStock' && .venv/bin/pip install -r requirements.txt"

mkdir -p "${DEPLOY_DIR}"
cp "${APP_DIR}/pythonStock/infra/aws/ecosystem.config.cjs" "${DEPLOY_DIR}/ecosystem.config.cjs"
chown -R "${APP_USER}:${APP_USER}" "${DEPLOY_DIR}"

run_as_app_user "pm2 startOrReload '${DEPLOY_DIR}/ecosystem.config.cjs' --update-env"
run_as_app_user "pm2 save"
systemctl restart pm2-ec2-user
systemctl reload nginx
EOF

  chmod +x /usr/local/bin/pythonstock-deploy.sh
}

dnf update -y
dnf install -y git nginx jq tar python3.11 python3.11-pip python3.11-devel gcc gcc-c++ make
if ! command -v aws >/dev/null 2>&1; then
  dnf install -y awscli || dnf install -y awscli-2
fi
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -
  dnf install -y nodejs
fi
if ! command -v pm2 >/dev/null 2>&1; then
  npm install -g pm2
fi

mkdir -p "${APP_ROOT}" "${DEPLOY_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_ROOT}"

systemctl disable --now pythonstock 2>/dev/null || true
rm -f /etc/systemd/system/pythonstock.service
systemctl daemon-reload

sync_source "${REPO_URL}" "${BRANCH}" "${APP_DIR}"
write_env_from_secret "${APP_ENV_SECRET_ARN}" "${AWS_REGION}"
install_python_deps
copy_pm2_config
write_nginx_config
write_deploy_script
start_pm2_app

systemctl restart nginx
