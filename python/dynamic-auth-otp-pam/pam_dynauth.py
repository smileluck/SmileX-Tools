#!/usr/bin/env python3

import os
import sys
import json
import socket
import logging

SOCKET_PATH = "/run/dynauth/dynauth.sock"
DYNAMIC_USERS_FILE = "/etc/dynauth/dynamic_users.conf"
LOG_FILE = "/var/log/dynauth.log"

# 只记录 WARNING 以上，避免密码泄漏
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.WARNING,
    format="%(asctime)s [PAM] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pam_dynauth")

PAM_SUCCESS = 0
PAM_AUTH_ERR = 1
PAM_IGNORE = 2


def load_dynamic_users():
    try:
        with open(DYNAMIC_USERS_FILE) as f:
            return {l.strip() for l in f if l.strip() and not l.startswith("#")}
    except FileNotFoundError:
        return set()


def query_dynauth_server(username: str, password: str) -> dict:
    """通过 Unix Socket 向 dynauth 服务查询"""
    payload = json.dumps({"username": username, "password": password}).encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(SOCKET_PATH)
            s.sendall(payload)
            resp = s.recv(1024).decode()
            return json.loads(resp)
    except Exception as e:
        logger.error(f"无法连接 dynauth 服务: {e}")
        return {"ok": False, "reason": "socket_error"}


def main():
    # 获取用户名
    username = os.environ.get("PAM_USER", "")
    if not username:
        sys.exit(PAM_IGNORE)

    # 读取密码（PAM 通过 stdin 传入）
    try:
        password = sys.stdin.readline().rstrip("\n")
    except Exception:
        password = ""

    dynamic_users = load_dynamic_users()

    if username not in dynamic_users:
        # 非动态用户，让 pam_unix 继续处理
        sys.exit(PAM_IGNORE)

    # 动态用户，走 OTP 验证
    result = query_dynauth_server(username, password)

    if result.get("ok") is True:
        sys.exit(PAM_SUCCESS)
    else:
        reason = result.get("reason", "unknown")
        logger.warning(f"动态认证失败: user={username} reason={reason}")
        sys.exit(PAM_AUTH_ERR)


if __name__ == "__main__":
    main()
