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
