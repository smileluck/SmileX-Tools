#!/usr/bin/env python3
"""
用户管理工具 (dynauth-admin)
==============================
用法：
  python3 dynauth_admin.py add-user   <username>   # 添加动态密码用户
  python3 dynauth_admin.py del-user   <username>   # 移除动态密码用户
  python3 dynauth_admin.py list-users              # 列出所有动态密码用户
  python3 dynauth_admin.py show-otp                # 显示当前所有用户 OTP
  python3 dynauth_admin.py gen-secret <username>   # 为用户生成新密钥
  python3 dynauth_admin.py get-otp    <username>   # 获取指定用户当前 OTP
  python3 dynauth_admin.py verify     <username> <otp>  # 验证 OTP（测试用）
"""

import os
import sys
import json
import hmac
import time
import struct
import secrets
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

DYNAMIC_USERS_FILE = "/etc/dynauth/dynamic_users.conf"
SECRETS_FILE       = "/etc/dynauth/secrets.json"
TIME_STEP          = 7200   # 2 小时
OTP_DIGITS         = 8
WINDOW             = 1

# ─────────────── TOTP 实现 ───────────────

def _hotp(secret_bytes: bytes, counter: int, digits: int = 8) -> str:
    msg = struct.pack(">Q", counter)
    h = hmac.new(secret_bytes, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)

def generate_totp(secret_hex: str, at: Optional[float] = None) -> str:
    ts = at if at is not None else time.time()
    counter = int(ts) // TIME_STEP
    return _hotp(bytes.fromhex(secret_hex), counter, OTP_DIGITS)

def verify_totp(secret_hex: str, token: str) -> bool:
    now = time.time()
    for delta in range(-WINDOW, WINDOW + 1):
        expected = generate_totp(secret_hex, at=now + delta * TIME_STEP)
        if hmac.compare_digest(expected, token.strip()):
            return True
    return False

# ─────────────── 文件操作 ───────────────

def ensure_dirs():
    os.makedirs("/etc/dynauth", exist_ok=True)
    Path(DYNAMIC_USERS_FILE).touch(exist_ok=True)
    if not Path(SECRETS_FILE).exists():
        Path(SECRETS_FILE).write_text("{}")
    # 权限保护
    os.chmod("/etc/dynauth", 0o700)
    os.chmod(SECRETS_FILE, 0o600)

def load_users() -> list:
    with open(DYNAMIC_USERS_FILE) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]

def save_users(users: list):
    with open(DYNAMIC_USERS_FILE, "w") as f:
        f.write("# 动态密码用户列表（每行一个用户名）\n")
        f.write("# 此文件由 dynauth-admin 管理，请勿手动修改\n\n")
        for u in sorted(set(users)):
            f.write(u + "\n")

def load_secrets() -> dict:
    with open(SECRETS_FILE) as f:
        return json.load(f)

def save_secrets(s: dict):
    with open(SECRETS_FILE, "w") as f:
        json.dump(s, f, indent=2)
    os.chmod(SECRETS_FILE, 0o600)

# ─────────────── 命令实现 ───────────────

def cmd_add_user(username: str):
    ensure_dirs()
    users = load_users()
    if username in users:
        print(f"[!] 用户 {username} 已在动态密码列表中")
        return

    secrets_data = load_secrets()
    if username not in secrets_data:
        # 自动生成密钥
        secret_hex = secrets.token_hex(20)  # 160-bit key
        secrets_data[username] = secret_hex
        save_secrets(secrets_data)
        print(f"[+] 已为 {username} 自动生成密钥")

    users.append(username)
    save_users(users)
    print(f"[+] 用户 {username} 已添加到动态密码组")

    # 展示首次 OTP
    otp = generate_totp(secrets_data[username])
    expires_in = TIME_STEP - (int(time.time()) % TIME_STEP)
    print(f"    当前 OTP : {otp}")
    print(f"    {expires_in // 60} 分 {expires_in % 60} 秒后更新")


def cmd_del_user(username: str):
    ensure_dirs()
    users = load_users()
    if username not in users:
        print(f"[!] 用户 {username} 不在动态密码列表中")
        return
    users = [u for u in users if u != username]
    save_users(users)
    print(f"[-] 用户 {username} 已从动态密码组移除（密钥已保留，如需删除请用 gen-secret 重置）")


def cmd_list_users():
    ensure_dirs()
    users = load_users()
    if not users:
        print("（当前无动态密码用户）")
        return
    print(f"\n动态密码用户列表（共 {len(users)} 个）：")
    secrets_data = load_secrets()
    for u in sorted(users):
        has_key = "✓ 有密钥" if u in secrets_data else "✗ 缺密钥"
        print(f"  {u:25s} [{has_key}]")
    print()


def cmd_show_otp():
    ensure_dirs()
    users = load_users()
    secrets_data = load_secrets()
    now = time.time()
    step_start = int(now) // TIME_STEP * TIME_STEP
    expires_in = TIME_STEP - (int(now) % TIME_STEP)

    print(f"\n{'═'*58}")
    print(f"  动态密码状态   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*58}")
    print(f"  时间窗口起始 : {datetime.fromtimestamp(step_start).strftime('%H:%M:%S')}")
    print(f"  下次更新倒计时: {expires_in // 60:02d}分{expires_in % 60:02d}秒")
    print(f"{'─'*58}")
    if not users:
        print("  （无动态密码用户）")
    for u in sorted(users):
        if u in secrets_data:
            otp = generate_totp(secrets_data[u])
            print(f"  {u:25s}  OTP: {otp}")
        else:
            print(f"  {u:25s}  [未配置密钥，请运行 gen-secret {u}]")
    print(f"{'═'*58}\n")


def cmd_gen_secret(username: str):
    ensure_dirs()
    secrets_data = load_secrets()
    new_secret = secrets.token_hex(20)
    secrets_data[username] = new_secret
    save_secrets(secrets_data)
    otp = generate_totp(new_secret)
    print(f"[+] 已为 {username} 生成新密钥")
    print(f"    当前 OTP: {otp}")
    print(f"    (密钥以十六进制存储于 {SECRETS_FILE}，请妥善保管)")


def cmd_get_otp(username: str):
    ensure_dirs()
    secrets_data = load_secrets()
    if username not in secrets_data:
        print(f"[!] 用户 {username} 无密钥，请先运行: dynauth-admin gen-secret {username}")
        sys.exit(1)
    otp = generate_totp(secrets_data[username])
    expires_in = TIME_STEP - (int(time.time()) % TIME_STEP)
    print(f"用户 {username} 的当前 OTP: {otp}  (还有 {expires_in // 60}分{expires_in % 60}秒过期)")


def cmd_verify(username: str, token: str):
    ensure_dirs()
    secrets_data = load_secrets()
    if username not in secrets_data:
        print(f"[!] 用户 {username} 无密钥")
        sys.exit(1)
    ok = verify_totp(secrets_data[username], token)
    print(f"验证结果: {'✓ 通过' if ok else '✗ 失败'}")
    sys.exit(0 if ok else 1)


# ─────────────── 主入口 ───────────────

USAGE = """
用法: dynauth-admin <命令> [参数]

命令列表:
  add-user   <用户名>              添加动态密码用户（自动生成密钥）
  del-user   <用户名>              从动态密码组移除用户
  list-users                       列出所有动态密码用户
  show-otp                         显示所有用户当前 OTP 及倒计时
  gen-secret <用户名>              为用户生成/重置密钥
  get-otp    <用户名>              获取指定用户的当前 OTP
  verify     <用户名> <OTP>        验证 OTP（测试用）
"""

def main():
    if os.geteuid() != 0:
        print("请以 root 身份运行此工具", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    if not args:
        print(USAGE)
        sys.exit(0)

    cmd = args[0]
    if cmd == "add-user" and len(args) == 2:
        cmd_add_user(args[1])
    elif cmd == "del-user" and len(args) == 2:
        cmd_del_user(args[1])
    elif cmd == "list-users":
        cmd_list_users()
    elif cmd == "show-otp":
        cmd_show_otp()
    elif cmd == "gen-secret" and len(args) == 2:
        cmd_gen_secret(args[1])
    elif cmd == "get-otp" and len(args) == 2:
        cmd_get_otp(args[1])
    elif cmd == "verify" and len(args) == 3:
        cmd_verify(args[1], args[2])
    else:
        print(USAGE)
        sys.exit(1)

if __name__ == "__main__":
    main()
