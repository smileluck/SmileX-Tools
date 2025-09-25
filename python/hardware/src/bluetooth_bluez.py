#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bluetooth通信模块 - 使用bluez库在Ubuntu系统下实现蓝牙数据收发

此模块提供了一个完整的蓝牙通信实现，包括设备搜索、连接建立、数据发送和接收功能。
适用于Ubuntu系统上的Python 3.6+环境。
"""

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
import time
import sys
from gi.repository import GLib
import threading
import logging

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BluetoothManager')

# 蓝牙相关常量
BLUEZ_SERVICE_NAME = 'org.bluez'
ADAPTER_INTERFACE = 'org.bluez.Adapter1'
DEVICE_INTERFACE = 'org.bluez.Device1'
GATT_SERVICE_INTERFACE = 'org.bluez.GattService1'
GATT_CHRC_INTERFACE = 'org.bluez.GattCharacteristic1'
GATT_DESC_INTERFACE = 'org.bluez.GattDescriptor1'

# 自定义服务UUID和特征UUID
SERVICE_UUID = '00001101-0000-1000-8000-00805F9B34FB'  # SPP服务UUID
CHRC_UUID = '00001101-0000-1000-8000-00805F9B34FB'     # SPP特征UUID

class BluetoothManager:
    """
    蓝牙管理器类 - 封装蓝牙设备搜索、连接、数据收发等功能
    """
    def __init__(self):
        """初始化蓝牙管理器"""
        self.bus = None
        self.mainloop = None
        self.adapter = None
        self.connected_device = None
        self.receive_callback = None
        self.is_connected = False
        self.rx_thread = None
        self.rx_stop_event = threading.Event()
        
    def initialize(self):
        """
        初始化蓝牙系统
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 初始化dbus主循环
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self.mainloop = GLib.MainLoop()
            
            # 获取系统总线
            self.bus = dbus.SystemBus()
            
            # 获取蓝牙适配器
            adapter_path = self._get_adapter_path()
            if not adapter_path:
                logger.error("无法找到蓝牙适配器")
                return False
            
            self.adapter = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, adapter_path),
                                         dbus.PROPERTIES_IFACE)
            
            # 开启蓝牙适配器
            self._power_on_adapter()
            
            logger.info("蓝牙初始化成功")
            return True
        except Exception as e:
            logger.error(f"蓝牙初始化失败: {str(e)}")
            return False
    
    def _get_adapter_path(self):
        """
        获取蓝牙适配器路径
        
        Returns:
            str: 蓝牙适配器路径，如/org/bluez/hci0
        """
        try:
            manager = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, "/"),
                                    "org.freedesktop.DBus.ObjectManager")
            objects = manager.GetManagedObjects()
            
            for path, interfaces in objects.items():
                if ADAPTER_INTERFACE in interfaces:
                    return path
            return None
        except Exception as e:
            logger.error(f"获取蓝牙适配器路径失败: {str(e)}")
            return None
    
    def _power_on_adapter(self):
        """开启蓝牙适配器电源"""
        try:
            self.adapter.Set(ADAPTER_INTERFACE, "Powered", dbus.Boolean(True))
            logger.info("蓝牙适配器已开启")
        except Exception as e:
            logger.error(f"开启蓝牙适配器失败: {str(e)}")
    
    def start_discovery(self, timeout=10):
        """
        开始搜索蓝牙设备
        
        Args:
            timeout (int): 搜索超时时间，单位秒
        
        Returns:
            list: 发现的蓝牙设备列表，每个设备包含name和address
        """
        try:
            # 开始发现设备
            adapter_props = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, self._get_adapter_path()),
                                         ADAPTER_INTERFACE)
            adapter_props.StartDiscovery()
            logger.info(f"开始搜索蓝牙设备，搜索时间{timeout}秒...")
            
            devices = []
            start_time = time.time()
            
            # 等待搜索完成
            while time.time() - start_time < timeout:
                time.sleep(1)
                
                # 获取已发现的设备
                manager = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, "/"),
                                        "org.freedesktop.DBus.ObjectManager")
                objects = manager.GetManagedObjects()
                
                for path, interfaces in objects.items():
                    if DEVICE_INTERFACE in interfaces:
                        device_props = interfaces[DEVICE_INTERFACE]
                        if "Name" in device_props and "Address" in device_props:
                            device = {
                                "name": device_props["Name"],
                                "address": device_props["Address"]
                            }
                            if device not in devices:
                                devices.append(device)
                                logger.info(f"发现设备: {device['name']} ({device['address']})")
            
            # 停止发现
            adapter_props.StopDiscovery()
            logger.info(f"设备搜索完成，共发现{len(devices)}个设备")
            
            return devices
        except Exception as e:
            logger.error(f"搜索蓝牙设备失败: {str(e)}")
            return []
    
    def connect(self, device_address):
        """
        连接到指定地址的蓝牙设备
        
        Args:
            device_address (str): 蓝牙设备MAC地址
        
        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info(f"尝试连接到设备: {device_address}")
            
            # 获取设备路径
            device_path = None
            manager = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, "/"),
                                    "org.freedesktop.DBus.ObjectManager")
            objects = manager.GetManagedObjects()
            
            for path, interfaces in objects.items():
                if DEVICE_INTERFACE in interfaces:
                    device_props = interfaces[DEVICE_INTERFACE]
                    if "Address" in device_props and device_props["Address"] == device_address:
                        device_path = path
                        break
            
            if not device_path:
                logger.error(f"未找到设备: {device_address}")
                return False
            
            # 获取设备接口
            device = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, device_path),
                                  DEVICE_INTERFACE)
            
            # 连接设备
            device.Connect()
            logger.info(f"成功连接到设备: {device_address}")
            
            self.connected_device = device
            self.is_connected = True
            
            # 启动接收线程
            self._start_receive_thread()
            
            return True
        except Exception as e:
            logger.error(f"连接设备失败: {str(e)}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """
        断开与当前连接设备的连接
        
        Returns:
            bool: 断开连接是否成功
        """
        try:
            if not self.connected_device:
                logger.warning("没有已连接的设备")
                return False
            
            # 停止接收线程
            self.rx_stop_event.set()
            if self.rx_thread and self.rx_thread.is_alive():
                self.rx_thread.join(2)
            
            # 断开连接
            self.connected_device.Disconnect()
            logger.info("已断开蓝牙连接")
            
            self.connected_device = None
            self.is_connected = False
            return True
        except Exception as e:
            logger.error(f"断开连接失败: {str(e)}")
            return False
    
    def send_data(self, data):
        """
        向已连接的设备发送数据
        
        Args:
            data (str or bytes): 要发送的数据
        
        Returns:
            bool: 发送是否成功
        """
        try:
            if not self.is_connected or not self.connected_device:
                logger.error("未连接到设备，无法发送数据")
                return False
            
            # 如果数据是字符串，转换为字节
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            
            # 查找GATT服务和特征
            manager = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, "/"),
                                    "org.freedesktop.DBus.ObjectManager")
            objects = manager.GetManagedObjects()
            
            # 遍历所有对象查找特征
            for path, interfaces in objects.items():
                if GATT_CHRC_INTERFACE in interfaces:
                    chrc_props = interfaces[GATT_CHRC_INTERFACE]
                    if "UUID" in chrc_props and chrc_props["UUID"] == CHRC_UUID:
                        # 找到特征，写入数据
                        char = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, path),
                                            GATT_CHRC_INTERFACE)
                        char.WriteValue(dbus.Array(data_bytes), {})
                        logger.info(f"发送数据: {data_bytes}")
                        return True
            
            logger.error(f"未找到特征: {CHRC_UUID}")
            return False
        except Exception as e:
            logger.error(f"发送数据失败: {str(e)}")
            return False
    
    def _start_receive_thread(self):
        """启动接收数据的线程"""
        self.rx_stop_event.clear()
        self.rx_thread = threading.Thread(target=self._receive_data)
        self.rx_thread.daemon = True
        self.rx_thread.start()
    
    def _receive_data(self):
        """接收数据的线程函数"""
        logger.info("启动数据接收线程")
        
        # 监听数据接收信号
        def signal_received_handler(*args, **kwargs):
            """信号接收处理函数"""
            try:
                # 解析接收到的数据
                value = args[0]
                data = bytes(value)
                logger.info(f"接收到数据: {data}")
                
                # 调用回调函数
                if self.receive_callback:
                    self.receive_callback(data)
            except Exception as e:
                logger.error(f"处理接收数据时出错: {str(e)}")
        
        # 查找特征并连接信号
        char_path = None
        manager = dbus.Interface(self.bus.get_object(BLUEZ_SERVICE_NAME, "/"),
                                "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()
        
        for path, interfaces in objects.items():
            if GATT_CHRC_INTERFACE in interfaces:
                chrc_props = interfaces[GATT_CHRC_INTERFACE]
                if "UUID" in chrc_props and chrc_props["UUID"] == CHRC_UUID:
                    char_path = path
                    break
        
        if char_path:
            # 连接PropertiesChanged信号
            self.bus.add_signal_receiver(
                signal_received_handler,
                signal_name="PropertiesChanged",
                dbus_interface="org.freedesktop.DBus.Properties",
                path=char_path
            )
        
        # 保持线程运行
        while not self.rx_stop_event.is_set():
            time.sleep(0.1)
        
        logger.info("数据接收线程已停止")
    
    def set_receive_callback(self, callback):
        """
        设置数据接收回调函数
        
        Args:
            callback (function): 接收数据时调用的函数，参数为接收到的数据
        """
        self.receive_callback = callback
    
    def run_mainloop(self):
        """运行蓝牙主循环"""
        try:
            if not self.mainloop:
                logger.error("主循环未初始化")
                return
            
            logger.info("启动蓝牙主循环")
            self.mainloop.run()
        except KeyboardInterrupt:
            logger.info("用户中断主循环")
        except Exception as e:
            logger.error(f"主循环异常: {str(e)}")
    
    def quit_mainloop(self):
        """退出蓝牙主循环"""
        if self.mainloop:
            logger.info("退出蓝牙主循环")
            self.mainloop.quit()

# 示例用法
if __name__ == '__main__':
    def data_received_handler(data):
        """数据接收处理函数示例"""
        print(f"接收到数据: {data}")
    
    # 创建蓝牙管理器实例
    bt_manager = BluetoothManager()
    
    # 初始化蓝牙
    if not bt_manager.initialize():
        print("蓝牙初始化失败")
        sys.exit(1)
    
    try:
        # 搜索设备
        devices = bt_manager.start_discovery()
        
        if devices:
            print("发现的蓝牙设备:")
            for i, device in enumerate(devices):
                print(f"{i+1}. 名称: {device['name']}, 地址: {device['address']}")
            
            # 示例：选择第一个设备进行连接
            if len(devices) > 0:
                choice = input("请输入要连接的设备编号 (输入q退出): ")
                if choice.lower() != 'q':
                    try:
                        index = int(choice) - 1
                        if 0 <= index < len(devices):
                            selected_device = devices[index]
                            
                            # 设置数据接收回调
                            bt_manager.set_receive_callback(data_received_handler)
                            
                            # 连接设备
                            if bt_manager.connect(selected_device['address']):
                                print(f"已连接到设备: {selected_device['name']}")
                                
                                # 启动数据发送线程
                                def send_thread_func():
                                    while bt_manager.is_connected:
                                        try:
                                            message = input("请输入要发送的消息 (输入q退出): ")
                                            if message.lower() == 'q':
                                                break
                                            bt_manager.send_data(message)
                                        except Exception as e:
                                            print(f"发送数据时出错: {str(e)}")
                                
                                send_thread = threading.Thread(target=send_thread_func)
                                send_thread.daemon = True
                                send_thread.start()
                                
                                # 启动主循环
                                bt_manager.run_mainloop()
                    except ValueError:
                        print("无效的输入")
    except KeyboardInterrupt:
        print("程序已中断")
    finally:
        # 断开连接并清理资源
        bt_manager.disconnect()
        bt_manager.quit_mainloop()
        print("程序已退出")