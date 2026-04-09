#!/usr/bin/env python3
"""
邮件通知服务 (dynauth_notify.py)
==================================
功能：在每个动态密码时间窗口切换时，自动将新 OTP 通过邮件发送给对应用户。
建议通过 cron 或 systemd timer 每 2 小时执行一次。

依赖：系统已配置 SMTP 或 sendmail，或修改下方 send_email() 使用 API 发送。
"""

import os
import sys
import json
import hmac
import time
import struct
import hashlib
import smtplib
import logging
from pathlib import Path
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional

# ───── 配置 ─────
DYNAMIC_USERS_FILE = "/etc/dynauth/dynamic_users.conf"
SECRETS_FILE       = "/etc/dynauth/secrets.json"
USER_EMAIL_FILE    = "/etc/dynauth/user_emails.json"  # {username: email}
TIME_STEP          = 7200
OTP_DIGITS         = 8

# SMTP 配置（按实际填写）
SMTP_HOST     = "smtp.example.com"
SMTP_PORT     = 587
SMTP_USER     = "noreply@example.com"
SMTP_PASSWORD = "your_smtp_password"
SMTP_FROM     = "系统通知 <noreply@example.com>"
# ────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("dynauth_notify")


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


def load_dynamic_users():
    with open(DYNAMIC_USERS_FILE) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def load_secrets():
    with open(SECRETS_FILE) as f:
        return json.load(f)


def load_emails():
    p = Path(USER_EMAIL_FILE)
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def send_email(to_addr: str, username: str, otp: str, valid_until: str):
    subject = f"【系统通知】您的动态登录密码已更新"
    body = f"""您好 {username}，

您的系统动态登录密码已经更新。

  当前动态密码：{otp}
  有效截止时间：{valid_until}

请在下次登录时使用上述密码。密码区分数字，请勿分享给他人。

如非本人操作，请联系系统管理员。

— 系统自动通知
"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = to_addr

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_USER, [to_addr], msg.as_string())
        logger.info(f"已发送 OTP 到 {to_addr} (用户: {username})")
    except Exception as e:
        logger.error(f"发送邮件失败 ({to_addr}): {e}")


def main():
    users   = load_dynamic_users()
    secrets = load_secrets()
    emails  = load_emails()
    now     = time.time()
    next_step_ts = (int(now) // TIME_STEP + 1) * TIME_STEP
    valid_until  = datetime.fromtimestamp(next_step_ts).strftime("%Y-%m-%d %H:%M:%S")

    for user in users:
        if user not in secrets:
            logger.warning(f"用户 {user} 无密钥，跳过")
            continue
        if user not in emails:
            logger.warning(f"用户 {user} 无邮件地址，跳过（请在 {USER_EMAIL_FILE} 中配置）")
            continue
        otp = generate_totp(secrets[user])
        send_email(emails[user], user, otp, valid_until)


if __name__ == "__main__":
    main()
