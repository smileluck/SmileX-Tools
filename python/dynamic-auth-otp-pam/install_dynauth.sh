#!/usr/bin/env bash
set -euo pipefail

# 动态密码认证系统安装脚本（Ubuntu）
# 用法：sudo bash install_dynauth.sh

APP_DIR="/usr/local/lib/dynauth"
ETC_DIR="/etc/dynauth"
RUN_DIR="/run/dynauth"
SERVICE_FILE="/etc/systemd/system/dynauth.service"
PAM_HELPER="${APP_DIR}/pam_dynauth.py"
SERVER_SCRIPT="${APP_DIR}/dynamic_password_server.py"
ADMIN_SCRIPT="${APP_DIR}/dynauth_admin.py"
NOTIFY_SCRIPT="${APP_DIR}/dynauth_notify.py"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "请以 root 身份运行：sudo bash install_dynauth.sh"
  exit 1
fi

echo "[1/8] 安装依赖"
apt update
apt install -y python3 python3-pip libpam-modules

echo "[2/8] 创建目录"
mkdir -p "$APP_DIR" "$ETC_DIR" "$RUN_DIR"
chmod 700 "$ETC_DIR"

echo "[3/8] 复制脚本"
install -m 0755 "$SCRIPT_DIR/dynamic_password_server.py" "$SERVER_SCRIPT"
install -m 0755 "$SCRIPT_DIR/pam_dynauth.py"         "$PAM_HELPER"
install -m 0755 "$SCRIPT_DIR/dynauth_admin.py"       "$ADMIN_SCRIPT"
install -m 0755 "$SCRIPT_DIR/dynauth_notify.py"      "$NOTIFY_SCRIPT"
install -m 0644 "$SCRIPT_DIR/dynauth.service"        "$SERVICE_FILE"

echo "[4/8] 初始化配置"
if [[ ! -f "$ETC_DIR/dynamic_users.conf" ]]; then
  cat > "$ETC_DIR/dynamic_users.conf" <<'EOF'
# 动态密码用户列表（每行一个）
# 例如：
# alice
# bob
EOF
fi

if [[ ! -f "$ETC_DIR/secrets.json" ]]; then
  echo '{}' > "$ETC_DIR/secrets.json"
fi

if [[ ! -f "$ETC_DIR/user_emails.json" ]]; then
  cat > "$ETC_DIR/user_emails.json" <<'EOF'
{}
EOF
fi

chmod 600 "$ETC_DIR/secrets.json" "$ETC_DIR/user_emails.json"
chmod 644 "$ETC_DIR/dynamic_users.conf"

echo "[5/8] 安装Python依赖（如需要）"
# 目前脚本仅使用标准库，此步骤保留以便后续扩展
python3 -m pip install --upgrade pip

echo "[6/8] 启用并启动服务"
systemctl daemon-reload
systemctl enable dynauth.service
systemctl restart dynauth.service
systemctl --no-pager --full status dynauth.service | cat

echo "[7/8] 备份并提示PAM配置"
if [[ -f /etc/pam.d/sshd && ! -f /etc/pam.d/sshd.bak.dynauth ]]; then
  cp /etc/pam.d/sshd /etc/pam.d/sshd.bak.dynauth
  echo "已备份 /etc/pam.d/sshd -> /etc/pam.d/sshd.bak.dynauth"
fi

echo ""
echo "请手工检查并替换 /etc/pam.d/sshd 的 auth 段为以下内容："
echo "------------------------------------------------------------"
cat "$SCRIPT_DIR/pam_sshd_dynauth.conf"
echo "------------------------------------------------------------"
echo ""

echo "[8/8] 完成"
echo "常用命令："
echo "  sudo $ADMIN_SCRIPT add-user <用户名>"
echo "  sudo $ADMIN_SCRIPT list-users"
echo "  sudo $ADMIN_SCRIPT show-otp"
echo "  sudo systemctl restart ssh"

echo "\n⚠️ 重要提醒：修改 PAM 之前请保持一个 root 会话不要断开，以免 SSH 配置错误导致锁在系统外。"