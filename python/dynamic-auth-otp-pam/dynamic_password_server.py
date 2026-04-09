#!/usr/bin/env python3
"""
动态密码服务器 (Dynamic Password Server)
=============================================
功能：
  - 为指定用户每 2 小时生成一个新的动态密码（TOTP 变体，时间步长 7200 秒）
  - 通过 Unix Domain Socket 提供验证接口
  - 普通用户走系统 /etc/shadow 验证，动态用户走本服务验证

依赖：
    pip3 install pyotp cryptography

作者：自动生成
"""

import os
import sys
import json
import hmac
import time
import struct
import hashlib
import socket
import logging
import threading
import subprocess
import socketserver
from pathlib import Path
from typing import Optional
from datetime import datetime

# ─────────────────────────────────────────────
# 配置区域（可按需修改）
# ─────────────────────────────────────────────

# 动态密码用户列表文件（每行一个用户名）
DYNAMIC_USERS_FILE = "/etc/dynauth/dynamic_users.conf"

# 每个用户的 HMAC 密钥文件（JSON 格式 {username: base32_secret}）
SECRETS_FILE = "/etc/dynauth/secrets.json"

# 服务监听的 Unix Socket 路径
SOCKET_PATH = "/run/dynauth/dynauth.sock"

# 日志文件
LOG_FILE = "/var/log/dynauth.log"

# 动态密码时间步长（秒）—— 每 2 小时更新一次
TIME_STEP = 7200  # 2 hours

# 动态密码长度
OTP_DIGITS = 8

# 允许的时间窗口偏移（向前/向后各允许 1 个步长，容忍时钟漂移）
WINDOW = 1

# ─────────────────────────────────────────────
# 日志初始化
# ─────────────────────────────────────────────

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("dynauth")


# ─────────────────────────────────────────────
# 核心：HOTP / TOTP 实现（不依赖 pyotp，纯标准库）
# ─────────────────────────────────────────────

def _hotp(secret_bytes: bytes, counter: int, digits: int = 8) -> str:
    """RFC 4226 HOTP 算法"""
    msg = struct.pack(">Q", counter)
    h = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def generate_totp(secret_hex: str, step: int = TIME_STEP, digits: int = OTP_DIGITS, at: Optional[float] = None) -> str:
    """
    基于 HMAC-SHA1 的 TOTP，时间步长可配置。
    secret_hex: 用户密钥（十六进制字符串，存储在 secrets.json 中）
    """
    ts = at if at is not None else time.time()
    counter = int(ts) // step
    secret_bytes = bytes.fromhex(secret_hex)
    return _hotp(secret_bytes, counter, digits)


def verify_totp(secret_hex: str, token: str, step: int = TIME_STEP, window: int = WINDOW) -> bool:
    """验证 TOTP，允许前后各 window 个时间步长的偏差"""
    now = time.time()
    for delta in range(-window, window + 1):
        expected = generate_totp(secret_hex, step=step, at=now + delta * step)
        if hmac.compare_digest(expected, token.strip()):
            return True
    return False


# ─────────────────────────────────────────────
# 用户管理
# ─────────────────────────────────────────────

def load_dynamic_users() -> set:
    """从配置文件加载需要动态密码的用户列表"""
    path = Path(DYNAMIC_USERS_FILE)
    if not path.exists():
        return set()
    users = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                users.add(line)
    return users


def load_secrets() -> dict:
    """加载用户密钥字典"""
    path = Path(SECRETS_FILE)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def is_dynamic_user(username: str) -> bool:
    return username in load_dynamic_users()


# ─────────────────────────────────────────────
# 认证逻辑
# ─────────────────────────────────────────────

def authenticate(username: str, password: str) -> dict:
    """
    统一认证入口。
    返回 {"ok": True/False, "reason": "..."}
    """
    if is_dynamic_user(username):
        secrets = load_secrets()
        if username not in secrets:
            logger.warning(f"动态用户 {username} 没有密钥，拒绝登录")
            return {"ok": False, "reason": "no_secret"}
        ok = verify_totp(secrets[username], password)
        logger.info(f"动态认证 user={username} result={'OK' if ok else 'FAIL'}")
        return {"ok": ok, "reason": "otp_ok" if ok else "otp_fail"}
    else:
        # 普通用户：委托给系统 PAM（通过 pam_unix 已处理，此分支仅作后备）
        return {"ok": None, "reason": "use_pam"}


# ─────────────────────────────────────────────
# Unix Socket 服务（供 PAM 脚本调用）
# ─────────────────────────────────────────────

class AuthHandler(socketserver.BaseRequestHandler):
    """处理来自 PAM exec 脚本的认证请求"""

    def handle(self):
        try:
            raw = self.request.recv(4096).decode("utf-8").strip()
            data = json.loads(raw)
            username = data.get("username", "")
            password = data.get("password", "")
            result = authenticate(username, password)
            self.request.sendall(json.dumps(result).encode("utf-8"))
        except Exception as e:
            logger.error(f"处理请求异常: {e}")
            self.request.sendall(json.dumps({"ok": False, "reason": "error"}).encode("utf-8"))


class UnixSocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def run_server():
    os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    with UnixSocketServer(SOCKET_PATH, AuthHandler) as server:
        os.chmod(SOCKET_PATH, 0o660)
        # 让 root 和 shadow 组都能访问
        try:
            import grp
            shadow_gid = grp.getgrnam("shadow").gr_gid
            os.chown(SOCKET_PATH, 0, shadow_gid)
        except Exception:
            pass

        logger.info(f"动态密码服务已启动，监听 {SOCKET_PATH}")
        logger.info(f"时间步长: {TIME_STEP}s ({TIME_STEP//3600}小时)")
        server.serve_forever()


# ─────────────────────────────────────────────
# 当前密码预览（调试 / 管理员工具）
# ─────────────────────────────────────────────

def show_current_passwords():
    """打印所有动态用户当前的 OTP 及过期时间"""
    users = load_dynamic_users()
    secrets = load_secrets()
    now = time.time()
    step_start = int(now) // TIME_STEP * TIME_STEP
    expires_in = TIME_STEP - (int(now) % TIME_STEP)

    print(f"\n{'='*55}")
    print(f"  动态密码状态  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print(f"{'='*55}")
    print(f"  时间步长: {TIME_STEP}s  |  下次更新: {expires_in//60}分{expires_in%60}秒后")
    print(f"  当前时间窗口起始: {datetime.fromtimestamp(step_start).strftime('%H:%M:%S')}")
    print(f"{'-'*55}")

    if not users:
        print("  （无动态密码用户）")
    for user in sorted(users):
        if user in secrets:
            otp = generate_totp(secrets[user])
            print(f"  用户: {user:20s}  当前OTP: {otp}")
        else:
            print(f"  用户: {user:20s}  [未配置密钥]")
    print(f"{'='*55}\n")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        show_current_passwords()
        sys.exit(0)

    if os.geteuid() != 0:
        print("请以 root 身份运行此服务", file=sys.stderr)
        sys.exit(1)

    run_server()
