#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
蓝牙服务端测试脚本

此脚本用于测试修改后的BluetoothManager类，演示如何创建蓝牙服务端，
等待其他设备主动连接，并进行数据收发。
"""

import sys
import time
import threading
import logging
from bluetooth_bluez import BluetoothManager

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BluetoothServerTest')

class BluetoothTest:
    """
    蓝牙服务端测试类
    提供完整的测试流程，包括初始化、启动广播、数据收发等功能
    """
    def __init__(self):
        """初始化测试类"""
        self.bt_manager = BluetoothManager()
        self.running = False
        self.send_thread = None
        
    def initialize(self, adapter_name='hci0', service_name='SmileX_Test_Server'):
        """
        初始化蓝牙服务端
        
        Args:
            adapter_name (str): 蓝牙适配器名称
            service_name (str): 蓝牙服务名称
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 初始化蓝牙管理器
            if not self.bt_manager.initialize(adapter_name=adapter_name, service_name=service_name):
                logger.error("蓝牙服务端初始化失败")
                return False
            
            # 设置数据接收回调
            self.bt_manager.set_receive_callback(self._data_received_handler)
            
            self.running = True
            logger.info("蓝牙服务端测试初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            return False
    
    def _data_received_handler(self, data):
        """
        数据接收处理函数
        
        Args:
            data (bytes): 接收到的数据
        """
        try:
            # 尝试解码接收到的数据
            message = data.decode('utf-8')
            logger.info(f"接收到数据: {message}")
            print(f"接收到数据: {message}")
            
            # 处理一些常见的测试命令
            if message.lower() == 'ping':
                logger.info("收到ping命令，回复pong")
                self.bt_manager.send_data('PONG')
            elif message.lower() == 'hello':
                logger.info("收到hello命令，回复world")
                self.bt_manager.send_data('WORLD')
            elif message.lower().startswith('echo:'):
                # 回显命令，将echo:后面的内容原样返回
                echo_content = message[5:]
                logger.info(f"收到回显命令，回显内容: {echo_content}")
                self.bt_manager.send_data(f"ECHO: {echo_content}")
        except Exception as e:
            logger.error(f"处理接收到的数据时出错: {str(e)}")
            print(f"处理接收到的数据时出错: {str(e)}")
            print(f"原始数据: {data}")
    
    def start(self):
        """
        启动蓝牙服务端测试
        
        Returns:
            bool: 启动是否成功
        """
        try:
            if not self.running:
                logger.error("测试类未初始化")
                return False
            
            # 开始广播
            if not self.bt_manager.start_advertising():
                logger.error("启动广播失败")
                return False
            
            # 启动发送测试线程
            self._start_send_thread()
            
            logger.info("蓝牙服务端测试已启动")
            print("蓝牙服务端测试已启动")
            print("等待客户端连接...")
            return True
        except Exception as e:
            logger.error(f"启动失败: {str(e)}")
            return False
    
    def _start_send_thread(self):
        """
        启动发送测试线程
        允许用户手动输入消息发送给已连接的设备
        """
        def send_thread_func():
            print("\n数据发送终端已启动")
            print("输入要发送的消息，或输入以下命令:")
            print("- 'list': 查看已连接设备")
            print("- 'exit': 退出程序")
            
            while self.running:
                try:
                    message = input("发送: ")
                    if message.lower() == 'exit':
                        self.stop()
                        break
                    elif message.lower() == 'list':
                        if self.bt_manager.connected_devices:
                            print(f"已连接设备数量: {len(self.bt_manager.connected_devices)}")
                            for addr in self.bt_manager.connected_devices:
                                print(f"- {addr}")
                        else:
                            print("暂无连接的设备")
                    else:
                        # 发送消息给所有已连接的设备
                        if not self.bt_manager.is_connected:
                            print("警告: 没有已连接的设备")
                        else:
                            success = self.bt_manager.send_data(message)
                            if not success:
                                print("发送失败，请检查日志")
                except Exception as e:
                    logger.error(f"发送数据时出错: {str(e)}")
                    print(f"发送数据时出错: {str(e)}")
                except EOFError:
                    # 处理Ctrl+D输入
                    break
        
        self.send_thread = threading.Thread(target=send_thread_func)
        self.send_thread.daemon = True
        self.send_thread.start()
    
    def stop(self):
        """
        停止蓝牙服务端测试
        """
        try:
            self.running = False
            
            # 停止广播
            self.bt_manager.stop_advertising()
            
            # 等待发送线程结束
            if self.send_thread and self.send_thread.is_alive():
                self.send_thread.join(2)
            
            logger.info("蓝牙服务端测试已停止")
        except Exception as e:
            logger.error(f"停止测试时出错: {str(e)}")

# 测试函数
def run_test():
    """
    运行蓝牙服务端测试
    """
    print("===== 蓝牙服务端测试程序 ======")
    print("此程序将创建一个蓝牙服务端，等待其他设备主动连接")
    
    # 创建测试实例
    test = BluetoothTest()
    
    # 获取用户输入的参数
    adapter_name = input("请输入蓝牙适配器名称 (默认: hci0): ") or 'hci0'
    service_name = input("请输入蓝牙服务名称 (默认: SmileX_Test_Server): ") or 'SmileX_Test_Server'
    
    # 初始化
    if not test.initialize(adapter_name=adapter_name, service_name=service_name):
        print("初始化失败，程序退出")
        return
    
    try:
        # 启动测试
        if not test.start():
            print("启动失败，程序退出")
            return
        
        # 保持主线程运行，直到用户中断
        while test.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        # 停止测试
        test.stop()
        print("===== 测试程序已退出 =====")

# 示例：自动化测试模式
def run_automated_test():
    """
    运行自动化测试
    此模式下，服务端会自动回复客户端发送的消息
    """
    print("===== 蓝牙服务端自动化测试模式 ======")
    
    # 创建测试实例
    test = BluetoothTest()
    
    # 初始化
    if not test.initialize(adapter_name='hci0', service_name='SmileX_Automated_Test'):
        print("初始化失败，程序退出")
        return
    
    # 自定义自动化测试的数据接收处理函数
    def automated_handler(data):
        try:
            message = data.decode('utf-8')
            logger.info(f"自动化测试接收到数据: {message}")
            print(f"自动化测试接收到数据: {message}")
            
            # 自动回复所有消息
            reply = f"AUTO_REPLY: {message}"
            test.bt_manager.send_data(reply)
            logger.info(f"自动回复: {reply}")
        except Exception as e:
            logger.error(f"自动化测试处理数据时出错: {str(e)}")
    
    # 设置自动化测试的回调函数
    test.bt_manager.set_receive_callback(automated_handler)
    
    try:
        # 启动测试
        if not test.start():
            print("启动失败，程序退出")
            return
        
        print("自动化测试已启动，将自动回复所有收到的消息")
        print("按Ctrl+C退出测试")
        
        # 保持主线程运行，直到用户中断
        while test.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        # 停止测试
        test.stop()
        print("===== 自动化测试程序已退出 =====")

if __name__ == '__main__':
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == '--automated':
        # 运行自动化测试模式
        run_automated_test()
    else:
        # 运行交互式测试模式
        run_test()#!/usr/bin/env python3
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