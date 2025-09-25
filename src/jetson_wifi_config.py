#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson无线配网主脚本

此脚本实现Jetson设备的无线配网功能，包括AP模式和STA模式的切换
- AP模式：Jetson创建Wi-Fi热点，等待用户连接并提供目标Wi-Fi信息
- STA模式：Jetson切换为客户端模式，连接到用户指定的Wi-Fi网络

作者: SmileX
版本: 1.1
日期: 2024-06-23
更新: 添加了自动检测无线网卡接口的功能
      添加了远程SSH操作功能，当通过Wi-Fi AP连接时通过SSH执行网络操作
"""
import os
import sys
import time
import json
import subprocess
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

# 尝试导入paramiko库，用于SSH连接
try:
    import paramiko
    SSH_AVAILABLE = True
except ImportError:
    print("警告: paramiko库未安装，SSH功能将不可用")
    print("请使用 'pip install paramiko' 安装paramiko库")
    SSH_AVAILABLE = False

# 远程服务器配置
REMOTE_SERVER_IP = "10.0.1.41"
# 远程操作时使用的SSH客户端
remote_ssh_client = None
# 标识当前是否通过AP模式连接
is_ap_connection = False

def get_wifi_interfaces():
    """
    获取系统上所有的无线网卡接口
    
    返回:
        list: 无线网卡接口名称列表
    """
    try:
        # 使用iwconfig命令检测无线网卡
        result = subprocess.run(['iwconfig'], capture_output=True, text=True)
        interfaces = []
        
        # 解析iwconfig输出，寻找无线接口
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and not line.startswith('\t') and 'IEEE' in line:
                interface = line.split(' ')[0]
                interfaces.append(interface)
        
        # 如果iwconfig不可用或没有找到接口，尝试使用ip命令
        if not interfaces:
            try:
                # 获取所有网络接口
                result = subprocess.run(['ip', 'link'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if 'state UP' in line or 'state DOWN' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            interface = parts[1].strip()
                            # 通常无线接口包含'wlan'、'wlp'或'wl'等字样
                            if 'wlan' in interface.lower() or 'wl' in interface.lower() and interface.lower() != 'lo':
                                interfaces.append(interface)
            except Exception:
                pass
        
        return interfaces
    except Exception as e:
        print(f"获取无线网卡接口时出错: {e}")
        return []

def connect_ssh_remote_server(remote_ip):
    """
    连接到远程服务器
    
    参数:
        remote_ip (str): 远程服务器IP地址
    
    返回:
        bool: 连接是否成功
    """
    global remote_ssh_client
    
    if not SSH_AVAILABLE:
        print("paramiko库未安装，无法连接到远程服务器")
        return False
        
    try:
        # 如果已经有连接，先关闭
        if remote_ssh_client:
            try:
                remote_ssh_client.close()
            except Exception:
                pass
            remote_ssh_client = None
        
        # 创建SSH客户端
        remote_ssh_client = paramiko.SSHClient()
        remote_ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 尝试使用密码和密钥两种方式连接
        try:
            # 首先尝试使用密钥认证
            print(f"尝试连接到远程服务器: {remote_ip} (密钥认证)...")
            remote_ssh_client.connect(remote_ip, timeout=10)
        except Exception as e1:
            try:
                # 如果密钥认证失败，尝试使用密码认证
                print(f"密钥认证失败: {e1}")
                print(f"尝试使用密码认证连接到远程服务器: {remote_ip}...")
                # 这里假设使用无密码登录或系统已配置SSH密钥
                # 如果需要密码，可以修改为: remote_ssh_client.connect(remote_ip, username='username', password='password')
                remote_ssh_client.connect(remote_ip, timeout=10)
            except Exception as e2:
                print(f"SSH连接失败: {e2}")
                remote_ssh_client = None
                return False
        
        if remote_ssh_client is None:
            return False
            
        print(f"已成功连接到远程服务器: {remote_ip}")
        return True
    except Exception as e:
        print(f"连接远程服务器时出错: {e}")
        if remote_ssh_client:
            try:
                remote_ssh_client.close()
            except Exception:
                pass
            remote_ssh_client = None
        return False

def run_remote_command(command):
    """
    在远程服务器上执行命令
    
    参数:
        command (str): 要执行的命令
    
    返回:
        tuple: (bool, str) - 命令是否成功执行和命令输出
    """
    global remote_ssh_client
    
    if not SSH_AVAILABLE or remote_ssh_client is None:
        return False, "SSH客户端不可用"
        
    try:
        stdin, stdout, stderr = remote_ssh_client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if exit_code != 0:
            return False, f"命令执行失败: {error}"
        
        return True, output
    except Exception as e:
        return False, f"执行远程命令时出错: {e}"

def close_ssh_connection():
    """
    关闭SSH连接
    """
    global remote_ssh_client
    
    if remote_ssh_client:
        try:
            remote_ssh_client.close()
            print("SSH连接已关闭")
        except Exception:
            pass
        finally:
            remote_ssh_client = None

def is_connected_via_ap():
    """
    检查当前是否通过AP模式连接
    
    返回:
        bool: 是否通过AP模式连接
    """
    global is_ap_connection
    
    try:
        # 检查当前IP地址是否在AP模式的IP范围内
        current_ip = get_local_ip()
        # AP模式通常使用10.0.0.x网段
        if current_ip.startswith('10.0.0.'):
            # 检查是否有AP模式的进程在运行
            try:
                result = subprocess.run(['pgrep', 'create_ap'], capture_output=True, text=True)
                if result.returncode == 0:
                    is_ap_connection = True
                    return True
            except Exception:
                pass
            
            # 检查接口配置
            result = subprocess.run(['ip', 'addr', 'show', DEFAULT_AP_INTERFACE], capture_output=True, text=True)
            if 'inet 10.0.0.' in result.stdout:
                is_ap_connection = True
                return True
    except Exception as e:
        print(f"检查连接模式时出错: {e}")
    
    is_ap_connection = False
    return False

# 默认配置
DEFAULT_AP_SSID = "JETSON_AP"
DEFAULT_AP_PASSWORD = "jetson-123"
# 获取无线网卡接口，如果没有找到则使用默认值
wifi_interfaces = get_wifi_interfaces()
DEFAULT_AP_INTERFACE = wifi_interfaces[0] if wifi_interfaces else "wlan0"
DEFAULT_AP_IP = "10.0.0.1"
DEFAULT_AP_PORT = 5000
CONFIG_FILE = "/etc/jetson_wifi_config.json"

def get_local_ip():
    """获取本机IP地址"""
    try:
        # 创建一个UDP套接字并连接到一个公共地址，获取本机IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

DEFAULT_AP_IP = get_local_ip()

DEFAULT_AP_PORT = 5000
CONFIG_FILE = "/etc/jetson_wifi_config.json"

class WifiConfigHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器，用于接收Wi-Fi配置信息"""
    
    def do_POST(self):
        """处理POST请求，接收Wi-Fi凭据"""
        if self.path == '/connect_wifi':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                # 尝试解析JSON数据
                data = json.loads(post_data)
            except json.JSONDecodeError:
                # 尝试解析表单数据
                data = parse_qs(post_data)
                # 转换为标准格式
                for key in data:
                    if isinstance(data[key], list) and len(data[key]) == 1:
                        data[key] = data[key][0]
            
            ssid = data.get('ssid')
            password = data.get('password')
            
            if not ssid or not password:
                self.send_response(400)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                response = json.dumps({"status": "error", "message": "SSID和密码是必需的"}, ensure_ascii=False)
                self.wfile.write(response.encode('utf-8'))
                return
            
            print(f"收到Wi-Fi凭据: SSID={ssid}")
            
            # 保存配置并尝试连接Wi-Fi
            save_wifi_config(ssid, password)
            success = connect_to_wifi(ssid, password)
            
            if success:
                # 连接成功，关闭AP模式
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                response = json.dumps({"status": "success", "message": "正在连接到Wi-Fi..."}, ensure_ascii=False)
                self.wfile.write(response.encode('utf-8'))
                
                # 在单独的线程中关闭AP模式
                import threading
                threading.Thread(target=switch_to_sta_mode).start()
            else:
                self.send_response(500)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                response = json.dumps({"status": "error", "message": "连接Wi-Fi失败"}, ensure_ascii=False)
                self.wfile.write(response.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            
    def do_GET(self):
        """处理GET请求，提供配网页面"""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            # 简单的HTML表单页面
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Jetson Wi-Fi配置</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 400px; margin: 0 auto; padding: 20px; }
                    h1 { text-align: center; }
                    .form-group { margin-bottom: 15px; }
                    label { display: block; margin-bottom: 5px; }
                    input[type="text"], input[type="password"] { width: 100%; padding: 8px; box-sizing: border-box; }
                    button { width: 100%; padding: 10px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
                    button:hover { background-color: #45a049; }
                    #status { margin-top: 20px; padding: 10px; border-radius: 5px; }
                    .success { background-color: #d4edda; color: #155724; }
                    .error { background-color: #f8d7da; color: #721c24; }
                </style>
            </head>
            <body>
                <h1>Jetson Wi-Fi配置</h1>
                <form id="wifiForm">
                    <div class="form-group">
                        <label for="ssid">Wi-Fi名称 (SSID):</label>
                        <input type="text" id="ssid" name="ssid" required>
                    </div>
                    <div class="form-group">
                        <label for="password">Wi-Fi密码:</label>
                        <input type="password" id="password" name="password" required>
                    </div>
                    <button type="submit">连接</button>
                </form>
                <div id="status"></div>
                
                <script>
                    document.getElementById('wifiForm').addEventListener('submit', function(e) {
                        e.preventDefault();
                        const ssid = document.getElementById('ssid').value;
                        const password = document.getElementById('password').value;
                        const statusDiv = document.getElementById('status');
                        
                        statusDiv.textContent = '正在连接...';
                        statusDiv.className = '';
                        
                        fetch('/connect_wifi', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ ssid: ssid, password: password })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                statusDiv.textContent = data.message;
                                statusDiv.className = 'success';
                                // 连接成功后，页面保持10秒然后刷新
                                setTimeout(() => {
                                    statusDiv.textContent = '连接成功！正在重新启动网络服务...';
                                }, 1000);
                            } else {
                                statusDiv.textContent = data.message;
                                statusDiv.className = 'error';
                            }
                        })
                        .catch(error => {
                            statusDiv.textContent = '请求失败: ' + error;
                            statusDiv.className = 'error';
                        });
                    });
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """重写日志方法，避免过多的控制台输出"""
        return

def is_root():
    """检查脚本是否以root权限运行"""
    return os.geteuid() == 0


def start_ap_mode(ssid=DEFAULT_AP_SSID, password=DEFAULT_AP_PASSWORD, interface=DEFAULT_AP_INTERFACE):
    """
    启动AP模式，创建Wi-Fi热点
    
    参数:
        ssid (str): Wi-Fi热点名称
        password (str): Wi-Fi热点密码
        interface (str): 无线网卡接口名称
    
    返回:
        tuple: (bool, Popen) - 操作是否成功和进程对象
    """
    try:
        print(f"正在配置{interface}为AP模式...")
        
        # 检查接口是否存在
        if not os.path.exists(f"/sys/class/net/{interface}"):
            print(f"错误: 接口{interface}不存在")
            return False, None
        
        # 检查接口是否为无线接口
        try:
            result = subprocess.run(['iwconfig', interface], capture_output=True, text=True)
            if 'no wireless extensions' in result.stderr:
                print(f"错误: 接口{interface}不是无线网卡")
                # 尝试自动选择其他无线接口
                wifi_interfaces = get_wifi_interfaces()
                if wifi_interfaces:
                    for iface in wifi_interfaces:
                        if iface != interface:
                            print(f"尝试使用接口{iface}...")
                            return start_ap_mode(ssid, password, iface)
                return False, None
        except Exception:
            print("警告: 无法验证接口类型，继续尝试...")
        
        # 检查create_ap是否安装
        try:
            subprocess.run(["which", "create_ap"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("create_ap已安装")
        except subprocess.CalledProcessError:
            print("create_ap未安装，正在安装...")
            # 注意：在生产环境中，应该先确认网络连接再执行安装
            # 这里只是示例，实际使用时可能需要先确保有网络连接
            print("请手动安装create_ap: git clone https://github.com/oblique/create_ap.git && cd create_ap && sudo make install")
            return False, None
        
        # 停止可能正在运行的create_ap实例
        subprocess.run(["sudo", "pkill", "create_ap"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 清除接口配置
        subprocess.run(["sudo", "ip", "addr", "flush", "dev", interface], check=True)
        
        # 启动AP模式
        # 使用&在后台运行，但在脚本中我们需要保持前台运行以提供Web服务
        ap_process = subprocess.Popen(
            ["sudo", "create_ap", interface, interface, ssid, password],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待AP模式启动
        time.sleep(5)
        
        # 检查AP是否成功启动
        ap_status = subprocess.run(["sudo", "create_ap", "--list-running"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if ssid in ap_status.stdout.decode('utf-8'):
            print(f"AP模式启动成功: {ssid}")
            return True, ap_process
        else:
            print("AP模式启动失败")
            return False, None
    except Exception as e:
        print(f"配置AP模式时出错: {e}")
        return False, None

def start_web_server(port=DEFAULT_AP_PORT):
    """
    启动Web服务器，用于接收Wi-Fi配置信息
    
    参数:
        port (int): 服务器端口号
    
    返回:
        HTTPServer: 服务器实例
    """
    server_address = ('', port)
    httpd = HTTPServer(server_address, WifiConfigHandler)
    print(f"Web服务器已启动，访问 http://{DEFAULT_AP_IP}:{port}/ 配置Wi-Fi")
    return httpd

def save_wifi_config(ssid, password):
    """
    保存Wi-Fi配置到文件
    
    参数:
        ssid (str): Wi-Fi名称
        password (str): Wi-Fi密码
    """
    config = {
        "ssid": ssid,
        "password": password,
        "timestamp": time.time()
    }
    
    try:
        # 确保配置文件所在目录存在
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        # 保存配置文件
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        
        # 设置文件权限，仅root可读写
        os.chmod(CONFIG_FILE, 0o600)
        print(f"Wi-Fi配置已保存到 {CONFIG_FILE}")
    except Exception as e:
        print(f"保存Wi-Fi配置时出错: {e}")

def load_wifi_config():
    """
    从文件加载Wi-Fi配置
    
    返回:
        dict或None: 配置信息或None（如果文件不存在或解析失败）
    """
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            return config
        return None
    except Exception as e:
        print(f"加载Wi-Fi配置时出错: {e}")
        return None

def connect_to_wifi(ssid, password, interface=DEFAULT_AP_INTERFACE, max_retries=3):
    """
    连接到指定的Wi-Fi网络，支持重试机制
    
    参数:
        ssid (str): Wi-Fi名称
        password (str): Wi-Fi密码
        interface (str): 无线网卡接口名称
        max_retries (int): 最大重试次数
    
    返回:
        bool: 连接是否成功
    """
    retries = 0
    
    while retries < max_retries:
        try:
            print(f"正在连接到Wi-Fi: {ssid} (尝试 {retries+1}/{max_retries})")
            
            # 先检查网络管理器是否运行
            nm_status = subprocess.run(
                ["sudo", "systemctl", "is-active", "NetworkManager"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            
            if nm_status.returncode != 0:
                print("警告: NetworkManager未运行，尝试启动...")
                subprocess.run(
                    ["sudo", "systemctl", "start", "NetworkManager"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                time.sleep(3)  # 等待NetworkManager启动
            
            # 方法1: 使用nmcli连接Wi-Fi
            result = subprocess.run(
                ["sudo", "nmcli", "device", "wifi", "connect", ssid, "password", password, "ifname", interface],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            
            if result.returncode == 0:
                print(f"成功连接到Wi-Fi: {ssid}")
                # 等待连接稳定
                time.sleep(5)
                # 验证连接
                if check_wifi_connection():
                    print("Wi-Fi连接已验证，网络可达")
                    return True
                else:
                    print("警告: 连接已建立，但无法访问网络")
                    retries += 1
                    time.sleep(3)
                    continue
            else:
                error_output = result.stderr.decode('utf-8')
                print(f"连接Wi-Fi失败: {error_output}")
                
                # 如果是认证失败，直接返回，不需要重试
                if "authentication failed" in error_output.lower() or "密码" in error_output:
                    print("认证失败，可能是密码错误")
                    return False
                
                retries += 1
                if retries < max_retries:
                    print("等待3秒后重试...")
                    time.sleep(3)
        except Exception as e:
            print(f"连接Wi-Fi时出错: {e}")
            retries += 1
            if retries < max_retries:
                print("等待3秒后重试...")
                time.sleep(3)
    
    # 所有重试都失败后，尝试使用iwconfig命令作为备选方法
    print("尝试使用备选方法连接Wi-Fi...")
    try:
        # 停止NetworkManager以避免冲突
        subprocess.run(["sudo", "systemctl", "stop", "NetworkManager"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 配置接口
        subprocess.run(["sudo", "ip", "link", "set", interface, "up"], check=True)
        time.sleep(1)
        
        # 使用iwconfig连接
        subprocess.run(["sudo", "iwconfig", interface, "essid", ssid, "key", password], check=True)
        time.sleep(2)
        
        # 配置IP（使用dhclient）
        subprocess.run(["sudo", "dhclient", interface], check=True)
        time.sleep(5)
        
        # 验证连接
        if check_wifi_connection():
            print("使用备选方法成功连接到Wi-Fi")
            return True
    except Exception as e:
        print(f"备选方法连接失败: {e}")
    finally:
        # 重新启动NetworkManager
        subprocess.run(["sudo", "systemctl", "start", "NetworkManager"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    print(f"连接Wi-Fi {ssid}失败，已达到最大重试次数")
    return False

def switch_to_sta_mode(interface=DEFAULT_AP_INTERFACE):
    """
    切换到STA模式，关闭AP服务
    
    参数:
        interface (str): 无线网卡接口名称
    """
    try:
        print("正在切换到STA模式...")
        
        # 停止create_ap进程
        subprocess.run(["sudo", "pkill", "create_ap"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 清除接口配置
        subprocess.run(["sudo", "ip", "addr", "flush", "dev", interface], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 重启NetworkManager服务
        subprocess.run(["sudo", "systemctl", "restart", "NetworkManager"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print("已切换到STA模式")
    except Exception as e:
        print(f"切换到STA模式时出错: {e}")

def check_wifi_connection():
    """
    检查Wi-Fi连接状态
    
    返回:
        bool: 是否已连接到Wi-Fi
    """
    try:
        # 尝试连接到一个公共DNS服务器
        socket.create_connection(('8.8.8.8', 53), timeout=5)
        return True
    except OSError:
        return False


def clear_nmcli_connections():
    """
    使用nmcli清空网络连接历史
    
    返回:
        bool: 操作是否成功
    """
    try:
        # 获取所有网络连接ID
        result = subprocess.run(
            ["sudo", "nmcli", "-t", "-f", "uuid", "connection"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        
        connections = result.stdout.strip().split('\n')
        for conn_id in connections:
            if conn_id:
                subprocess.run(
                    ["sudo", "nmcli", "connection", "delete", conn_id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True
                )
        print("已清空网络连接历史")
        return True
    except Exception as e:
        print(f"清空网络连接历史时出错: {e}")
        return False

def main():
    """主函数"""
    # 检查是否以root权限运行
    if not is_root():
        print("错误: 此脚本需要以root权限运行")
        print("请使用 sudo python jetson_wifi_config.py 命令运行")
        sys.exit(1)
        
    
    # 显示检测到的无线网卡接口
    wifi_interfaces = get_wifi_interfaces()
    print(f"检测到的无线网卡接口: {', '.join(wifi_interfaces) if wifi_interfaces else '未找到'}")
    print(f"当前使用的接口: {DEFAULT_AP_INTERFACE}")
    

    # 在主函数中合适位置调用该函数，例如在检查root权限之后
    if clear_nmcli_connections():
        print("已清空网络连接历史")
    else:
        print("清空网络连接历史失败")

    # 检查是否已连接到Wi-Fi
    # if check_wifi_connection():
    #     print("已连接到Wi-Fi网络，无需配置")
    #     sys.exit(0)
    
    # 尝试加载已保存的Wi-Fi配置
    config = load_wifi_config()
    if config:
        print("发现已保存的Wi-Fi配置，尝试连接...")
        ssid = config.get('ssid')
        password = config.get('password')
        
        if ssid and password:
            if connect_to_wifi(ssid, password):
                print("使用已保存的配置成功连接到Wi-Fi")
                sys.exit(0)
            else:
                print("使用已保存的配置连接Wi-Fi失败，启动AP模式...")
    
    # 启动AP模式
    # ap_success, ap_process = start_ap_mode()
    # if not ap_success:
    #     print("无法启动AP模式，尝试手动配置...")
    #     # 这里可以添加手动配置AP模式的代码
    #     sys.exit(1)
    
    # 启动Web服务器
    try:
        httpd = start_web_server()
        # 保持Web服务器运行
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("正在关闭Web服务器...")
        httpd.server_close()
    finally:
        # 确保AP模式已关闭
        # if ap_process:
        #     ap_process.terminate()
        #     ap_process.wait()
        
        # 切换回STA模式
        switch_to_sta_mode()

if __name__ == '__main__':
    main()
