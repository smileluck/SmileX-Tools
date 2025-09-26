import socket
import threading
import subprocess


class BluetoothServer:
    def __init__(self, channel=1, bluetooth_name=None):
        self.channel = channel
        self.server_socket = None
        self.is_running = False
        # 获取本地蓝牙适配器的MAC地址（解决地址错误的关键）
        self.local_mac = self._get_local_mac()
        print(f"local_mac=>{self.local_mac}")

        # 如果提供了蓝牙名称，则设置蓝牙适配器名称
        if bluetooth_name:
            self.set_bluetooth_name(bluetooth_name)

    def _get_local_mac(self):
        """获取本地蓝牙适配器的MAC地址（hci0）"""
        try:
            result = subprocess.check_output(["hciconfig", "hci0"], text=True)
            # 从输出中提取MAC地址（格式：AA:BB:CC:DD:EE:FF）
            for line in result.split("\n"):
                if "BD Address" in line:
                    line = line.split(": ")[1].strip()
                    return line.split(" ")[0].strip()

            return ""  # 未找到时留空
        except subprocess.CalledProcessError:
            return ""

    def set_bluetooth_name(self, name):
        """设置蓝牙适配器的名称

        Args:
            name (str): 要设置的蓝牙名称

        Returns:
            bool: 设置是否成功
        """
        try:
            # 使用hciconfig命令设置蓝牙名称
            subprocess.run(["hciconfig", "hci0", "name", name], check=True)
            print(f"蓝牙名称已设置为: {name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"设置蓝牙名称失败: {e}")
            return False

    def start(self):
        if not self.local_mac:
            print("警告：未找到蓝牙适配器MAC地址，尝试使用默认配置")

        try:
            # 创建蓝牙Socket
            self.server_socket = socket.socket(
                socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
            )

            # 绑定到本地适配器的MAC地址（而非空字符串）
            # 若local_mac为空，自动回退到空字符串
            self.server_socket.bind((self.local_mac, self.channel))
            self.server_socket.listen(1)
            self.is_running = True
            print(f"服务器启动成功，监听 {self.local_mac} 通道 {self.channel}...")

            threading.Thread(target=self._accept_connections, daemon=True).start()
            return True

        except OSError as e:
            print(f"服务器启动失败: {e}")
            self.stop()
            return False

    def _accept_connections(self):
        while self.is_running:
            client_socket, client_addr = self.server_socket.accept()
            print(f"新连接: {client_addr}")

            while self.is_running:
                data = client_socket.recv(1024)
                if not data:
                    break
                print(f"收到: {data.decode('utf-8')}")
                client_socket.sendall(b"receive")

            client_socket.close()
            print("连接断开")

    def stop(self):
        self.is_running = False
        if self.server_socket:
            self.server_socket.close()
        print("服务器已停止")


if __name__ == "__main__":
    server = BluetoothServer(channel=1, bluetooth_name="WUJIE-BT")
    if server.start():
        try:
            input("按Ctrl+C停止服务器...\n")
        except KeyboardInterrupt:
            server.stop()
