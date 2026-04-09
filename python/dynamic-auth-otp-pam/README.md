# Dynamic Auth OTP PAM

## 简介

Dynamic Auth OTP PAM 是一个基于 TOTP（Time-based One-Time Password）的动态密码认证系统，专为 Linux SSH 登录安全而设计。该模块实现了双轨认证机制：动态密码用户使用 OTP 认证，普通用户继续使用系统密码认证。

**核心特性：**
- 基于 RFC 6238 TOTP 标准实现
- 每 2 小时自动更新动态密码
- 支持邮件自动通知用户当前 OTP
- 支持用户密钥的生成、管理和验证
- 提供 systemd 服务管理

## 架构说明

### 组件架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        SSH Client                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PAM 认证层                                   │
│  ┌─────────────────────┐      ┌─────────────────────┐          │
│  │  pam_dynauth.py     │      │    pam_unix.so      │          │
│  │  (OTP 验证)          │      │   (系统密码验证)     │          │
│  └──────────┬──────────┘      └─────────────────────┘          │
│             │                                                     │
└─────────────┼───────────────────────────────────────────────────┘
              │ Unix Socket
              ▼
┌─────────────────────────────────────────────────────────────────┐
│            dynamic_password_server.py                            │
│                     (Dynauth Server)                             │
│  ┌─────────────────┐      ┌─────────────────┐                   │
│  │  TOTP Generator │      │  Auth Verifier  │                   │
│  │  (密码生成)      │      │   (密码验证)     │                   │
│  └─────────────────┘      └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   配置存储层                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ dynamic_users    │  │   secrets.json   │  │ user_emails    │ │
│  │ .conf            │  │   (用户密钥)      │  │ .json          │ │
│  └──────────────────┘  └──────────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 核心文件说明

| 文件 | 功能描述 |
|------|----------|
| `dynamic_password_server.py` | 动态密码服务器，通过 Unix Socket 提供 TOTP 验证服务 |
| `pam_dynauth.py` | PAM 认证模块，作为 SSH 登录的二次认证入口 |
| `dynauth_admin.py` | 用户管理工具CLI，用于管理动态密码用户和密钥 |
| `dynauth_notify.py` | 邮件通知服务，在密码时间窗口切换时自动发送 OTP 给用户 |
| `install_dynauth.sh` | 自动化安装脚本，支持 Ubuntu 系统一键部署 |
| `system_config/dynauth.service` | systemd 服务单元文件 |

## 安装指南

### 环境要求

- **操作系统**: Ubuntu 20.04+ / Debian 11+
- **Python**: Python 3.8+
- **管理员权限**: root 权限

### 自动安装

```bash
cd python/dynamic-auth-otp-pam
chmod +x install_dynauth.sh
sudo bash install_dynauth.sh
```

安装脚本会自动完成以下操作：
1. 安装系统依赖（python3、python3-pip、libpam-modules）
2. 创建必要的目录结构
3. 复制脚本到系统目录
4. 初始化配置文件
5. 启用并启动 dynauth 服务
6. 提示 PAM 配置修改

### 手动安装

```bash
# 1. 创建目录
sudo mkdir -p /usr/local/lib/dynauth /etc/dynauth /run/dynauth

# 2. 复制脚本
sudo cp dynamic_password_server.py /usr/local/lib/dynauth/
sudo cp pam_dynauth.py /usr/local/lib/dynauth/
sudo cp dynauth_admin.py /usr/local/lib/dynauth/
sudo cp dynauth_notify.py /usr/local/lib/dynauth/

# 3. 设置权限
sudo chmod 700 /etc/dynauth
sudo chmod 600 /etc/dynauth/secrets.json

# 4. 安装 systemd 服务
sudo cp system_config/dynauth.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dynauth.service
sudo systemctl start dynauth.service

# 5. 配置 PAM
# 参考 pam_sshd_dynauth.conf 修改 /etc/pam.d/sshd
```

## 使用方法

### 用户管理

```bash
# 添加动态密码用户（自动生成密钥）
sudo dynauth-admin add-user <username>

# 从动态密码组移除用户
sudo dynauth-admin del-user <username>

# 列出所有动态密码用户
sudo dynauth-admin list-users

# 显示所有用户当前 OTP 及倒计时
sudo dynauth-admin show-otp

# 为用户生成新密钥
sudo dynauth-admin gen-secret <username>

# 获取指定用户的当前 OTP
sudo dynauth-admin get-otp <username>

# 验证 OTP（测试用）
sudo dynauth-admin verify <username> <otp>
```

### 邮件通知配置

编辑 `/etc/dynauth/user_emails.json`：

```json
{
  "username1": "user1@example.com",
  "username2": "user2@example.com"
}
```

配置 SMTP 服务器参数（编辑 `dynauth_notify.py` 中的配置）：

```python
SMTP_HOST = "smtp.example.com"
SMTP_PORT = 587
SMTP_USER = "noreply@example.com"
SMTP_PASSWORD = "your_smtp_password"
SMTP_FROM = "系统通知 <noreply@example.com>"
```

设置定时任务（每 2 小时执行）：

```bash
# 编辑 crontab
sudo crontab -e

# 添加以下行
0 */2 * * * /usr/local/lib/dynauth/dynauth_notify.py
```

### 服务管理

```bash
# 查看服务状态
sudo systemctl status dynauth.service

# 重启服务
sudo systemctl restart dynauth.service

# 查看日志
sudo journalctl -u dynauth.service -f
```

## 配置说明

### 配置文件

| 文件路径 | 描述 | 权限 |
|----------|------|------|
| `/etc/dynauth/dynamic_users.conf` | 动态密码用户列表（每行一个用户名） | 644 |
| `/etc/dynauth/secrets.json` | 用户密钥存储（JSON格式） | 600 |
| `/etc/dynauth/user_emails.json` | 用户邮箱映射（JSON格式） | 600 |
| `/var/log/dynauth.log` | 认证服务日志 | - |

### 密钥说明

- **密钥生成**: 使用 `secrets.token_hex(20)` 生成 160-bit 随机密钥
- **存储格式**: 十六进制字符串存储在 `secrets.json` 中
- **OTP 生成**: 基于 HMAC-SHA1 的 TOTP 算法，8位数字
- **时间步长**: 7200秒（2小时）

### PAM 配置

编辑 `/etc/pam.d/sshd`，将 `auth` 部分替换为：

```
auth  [success=done ignore=ignore auth_err=die default=bad]  pam_exec.so  expose_authtok  /usr/local/lib/dynauth/pam_dynauth.py
auth  required  pam_unix.so  nullok_secure

@include common-account
@include common-password
@include common-session
@include common-session-noninteractive
```

**认证流程说明：**
1. `pam_exec` 调用 `pam_dynauth.py`
   - 动态用户：OTP 正确返回 success，错误返回 auth_err
   - 非动态用户：返回 ignore，继续执行下一行
2. `pam_unix` 处理非动态用户的系统密码验证

## 安全特性

1. **密钥保护**: `/etc/dynauth` 目录权限 700，`secrets.json` 文件权限 600
2. **日志安全**: 仅记录 WARNING 以上级别，防止密码泄漏
3. **时间窗口**: 允许前后各 1 个时间步长的偏差，容忍时钟漂移
4. **Socket 权限**: 仅允许 root 和 shadow 组访问 Unix Socket
5. **systemd 安全加固**:
   - `ProtectSystem=strict`: 限制文件系统访问
   - `ProtectHome=true`: 禁止访问 /home
   - `NoNewPrivileges=true`: 禁止提权
   - `PrivateTmp=true`: 使用私有 tmp 目录

## 故障排除

### SSH 连接失败

1. 检查 dynauth 服务状态：
```bash
sudo systemctl status dynauth.service
```

2. 查看认证日志：
```bash
sudo tail -f /var/log/dynauth.log
```

3. 确认用户在动态用户列表中：
```bash
sudo dynauth-admin list-users
```

4. 检查 OTP 是否正确：
```bash
sudo dynauth-admin show-otp
```

### 邮件通知失败

1. 手动测试邮件发送：
```bash
python3 dynauth_notify.py
```

2. 检查 SMTP 配置是否正确

3. 确认邮件地址配置：
```bash
cat /etc/dynauth/user_emails.json
```

### 被锁定在系统外

**警告**: 修改 PAM 配置前，请务必保持一个 root 会话不要断开！

如果 SSH 配置错误导致无法登录：
1. 通过控制台或物理登录进入系统
2. 恢复 PAM 配置：
```bash
sudo cp /etc/pam.d/sshd.bak.dynauth /etc/pam.d/sshd
```
3. 重启 SSH 服务：
```bash
sudo systemctl restart ssh
```

## 工作原理

### TOTP 算法

```
TOTP = HOTP(SecretKey, floor(Timestamp / TimeStep))

其中：
- SecretKey: 用户唯一密钥
- Timestamp: 当前 Unix 时间戳
- TimeStep: 时间步长（默认 7200 秒）
- HOTP: RFC 4226 定义的 HMAC-Based OTP 算法
```

### 认证流程

```
1. 用户登录时输入: username + password(OTP)
2. PAM 调用 pam_dynauth.py
3. pam_dynauth.py 通过 Unix Socket 查询 dynauth server
4. dynauth server 根据时间步长计算当前 OTP
5. 比较用户输入的 OTP 与计算值
6. 返回认证结果
```

## 许可证

本项目遵循 MIT 许可证。

## 联系方式

- 项目地址: https://github.com/smileluck/SmileX-Tools
