# 要发送的WiFi信息
wifi_ssid = "robot-2.4"
wifi_password = "MyPassword123"

# 构造数据：SSID长度 + SSID + 密码长度 + 密码
ssid_bytes = wifi_ssid.encode("utf-8")
password_bytes = wifi_password.encode("utf-8")

data = [
    len(ssid_bytes),  # SSID长度（1字节）
    *ssid_bytes,  # SSID内容
    len(password_bytes),  # 密码长度（1字节）
    *password_bytes,  # 密码内容
]

