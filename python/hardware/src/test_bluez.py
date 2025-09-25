#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bluetooth Bluez模块测试脚本

此脚本演示如何使用bluetooth_bluez.py模块进行蓝牙设备搜索、连接和数据收发。
"""

import sys
import os
import time
import logging

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入蓝牙管理器模块
from bluetooth_bluez import BluetoothManager

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BluetoothTest')

class BluetoothTest:
    """
    蓝牙功能测试类
    """
    def __init__(self):
        """初始化测试类"""
        self.bt_manager = BluetoothManager()
        self.is_test_running = False
    
    def on_data_received(self, data):
        """
        数据接收回调函数
        
        Args:
            data (bytes): 接收到的数据
        """
        try:
            # 尝试将接收到的数据解码为字符串
            message = data.decode('utf-8')
            print(f"\n[接收] {message}")
        except UnicodeDecodeError:
            print(f"\n[接收] 无法解码的数据: {data}")
    
    def start_test(self):
        """
        开始蓝牙功能测试
        """
        print("===== 蓝牙功能测试开始 =====")
        
        # 初始化蓝牙
        if not self.bt_manager.initialize():
            print("错误: 蓝牙初始化失败，请检查您的蓝牙适配器是否正常工作")
            return False
        
        self.is_test_running = True
        
        try:
            # 搜索设备
            print("搜索蓝牙设备中...")
            devices = self.bt_manager.start_discovery(timeout=8)
            
            if not devices:
                print("未发现任何蓝牙设备，请确保周围有可发现的蓝牙设备")
                return False
            
            # 显示发现的设备
            print("\n发现的蓝牙设备:")
            for i, device in enumerate(devices):
                print(f"{i+1}. 名称: {device['name']}, 地址: {device['address']}")
            
            # 让用户选择要连接的设备
            while True:
                choice = input("\n请输入要连接的设备编号 (输入q退出): ")
                if choice.lower() == 'q':
                    print("测试已取消")
                    return False
                
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(devices):
                        selected_device = devices[index]
                        break
                    else:
                        print(f"无效的选择，请输入1-{len(devices)}之间的数字")
                except ValueError:
                    print("无效的输入，请输入数字")
            
            # 设置数据接收回调
            self.bt_manager.set_receive_callback(self.on_data_received)
            
            # 连接设备
            print(f"\n正在连接到设备: {selected_device['name']} ({selected_device['address']})...")
            if not self.bt_manager.connect(selected_device['address']):
                print(f"错误: 无法连接到设备 {selected_device['name']}")
                return False
            
            print(f"成功连接到设备: {selected_device['name']}")
            print("\n===== 连接已建立，可以开始通信 =====")
            print("输入要发送的消息，输入'q'退出，输入'clear'清屏")
            print("==================================")
            
            # 启动数据发送循环
            while self.is_test_running and self.bt_manager.is_connected:
                try:
                    message = input("\n[发送] ")
                    
                    if message.lower() == 'q':
                        print("退出通信")
                        break
                    elif message.lower() == 'clear':
                        os.system('cls' if os.name == 'nt' else 'clear')
                        continue
                    
                    # 发送数据
                    if not self.bt_manager.send_data(message):
                        print("警告: 数据发送失败")
                except KeyboardInterrupt:
                    print("\n用户中断输入")
                    break
                except Exception as e:
                    print(f"输入处理错误: {str(e)}")
            
        except Exception as e:
            print(f"测试过程中发生错误: {str(e)}")
            return False
        finally:
            # 断开连接
            self.cleanup()
        
        print("\n===== 蓝牙功能测试结束 =====")
        return True
    
    def cleanup(self):
        """清理资源并断开连接"""
        self.is_test_running = False
        
        # 断开蓝牙连接
        if hasattr(self, 'bt_manager'):
            self.bt_manager.disconnect()
            self.bt_manager.quit_mainloop()

# 主函数
if __name__ == '__main__':
    print("\n欢迎使用蓝牙Bluez模块测试工具")
    print("此工具将帮助您测试蓝牙设备的搜索、连接和数据传输功能")
    print("\n注意事项:")
    print("1. 请确保您的Ubuntu系统已安装bluez库")
    print("2. 运行此脚本可能需要root权限")
    print("3. 请确保蓝牙适配器已启用并处于可发现状态")
    
    # 检查是否以root权限运行
    if os.geteuid() != 0:
        print("\n警告: 此脚本需要root权限才能正常工作")
        print("请使用 sudo python3 test_bluez.py 命令运行")
        sys.exit(1)
    
    # 等待用户确认
    input("\n按Enter键继续...")
    
    # 创建测试实例并开始测试
    test = BluetoothTest()
    test.start_test()