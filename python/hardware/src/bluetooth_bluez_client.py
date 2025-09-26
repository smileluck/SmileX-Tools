#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bluetooth通信模块 - 使用bless库在Ubuntu系统下实现蓝牙服务端功能

此模块提供了一个完整的蓝牙服务端实现，等待其他设备主动连接，
支持数据发送和接收功能。适用于Ubuntu系统上的Python 3.6+环境。
"""

import time
import sys
import threading
import logging
from bless import BlessServer, BlessGATTCharacteristic
from bless.backends.bluezdbus.characteristic import BlueZGATTCharacteristic

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('BluetoothManager')

# 蓝牙相关常量
SERVICE_UUID = '00001101-0000-1000-8000-00805F9B34FB'  # 服务UUID
CHRC_UUID = '00001102-0000-1000-8000-00805F9B34FB'     # 特征UUID

class BluetoothManager:
    """
    蓝牙管理器类 - 使用bless库封装蓝牙服务端功能，等待其他设备主动连接
    提供数据收发、连接管理等功能
    """
    def __init__(self):
        """初始化蓝牙管理器"""
        self.server = None
        self.adapter_name = 'hci0'  # 默认蓝牙适配器名称
        self.service_uuid = SERVICE_UUID
        self.characteristic_uuid = CHRC_UUID
        self.receive_callback = None
        self.is_connected = False
        self.connected_devices = set()
        self.rx_thread = None
        self.rx_stop_event = threading.Event()
        
    def initialize(self, adapter_name='hci0', service_name='SmileX_Bluetooth_Server'):
        """
        初始化蓝牙服务端
        
        Args:
            adapter_name (str): 蓝牙适配器名称
            service_name (str): 蓝牙服务名称
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.adapter_name = adapter_name
            self.service_name = service_name
            
            # 创建蓝牙服务端
            self.server = BlessServer(name=self.service_name, adapter=self.adapter_name)
            
            # 设置连接回调
            self.server.on_connect = self._on_device_connect
            self.server.on_disconnect = self._on_device_disconnect
            
            # 添加服务和特征
            self._add_service_and_characteristic()
            
            logger.info("蓝牙服务端初始化成功")
            return True
        except Exception as e:
            logger.error(f"蓝牙服务端初始化失败: {str(e)}")
            return False
    
    def _add_service_and_characteristic(self):
        """添加蓝牙服务和特征"""
        try:
            # 创建特征属性
            char_props = {
                'Characteristic': {
                    'Permissions': ['read', 'write', 'notify'],
                    'Properties': {
                        'Value': []
                    },
                    'Descriptors': {
                        '2901': {
                            'Value': 'SmileX Bluetooth Data'
                        },
                        '2902': {
                            'Value': {
                                'ClientCharacteristicConfiguration': 0
                            }
                        }
                    }
                }
            }
            
            # 添加服务和特征到服务器
            self.server.add_gatt_service(self.service_uuid)
            self.server.add_gatt_characteristic(
                self.service_uuid, 
                self.characteristic_uuid, 
                char_props
            )
            
            # 设置特征读取回调
            self.server.read_request_func = self._on_read_request
            self.server.write_request_func = self._on_write_request
            
        except Exception as e:
            logger.error(f"添加服务和特征失败: {str(e)}")
    
    def _on_device_connect(self, device_address):
        """
        设备连接回调函数
        
        Args:
            device_address (str): 连接的设备地址
        """
        logger.info(f"设备已连接: {device_address}")
        self.connected_devices.add(device_address)
        self.is_connected = True
    
    def _on_device_disconnect(self, device_address):
        """
        设备断开连接回调函数
        
        Args:
            device_address (str): 断开连接的设备地址
        """
        logger.info(f"设备已断开: {device_address}")
        if device_address in self.connected_devices:
            self.connected_devices.remove(device_address)
        
        # 如果没有设备连接，则更新连接状态
        if not self.connected_devices:
            self.is_connected = False
    
    def _on_read_request(self, characteristic, **kwargs):
        """
        处理读取请求
        
        Args:
            characteristic: 请求读取的特征
            **kwargs: 其他参数
            
        Returns:
            bytes: 要返回的数据
        """
        logger.info(f"收到读取请求: {characteristic.uuid}")
        # 默认返回空数据，可以根据需求修改
        return b''
    
    def _on_write_request(self, characteristic, value, **kwargs):
        """
        处理写入请求
        
        Args:
            characteristic: 请求写入的特征
            value (bytes): 写入的数据
            **kwargs: 其他参数
        """
        logger.info(f"收到写入请求: {characteristic.uuid}, 数据: {value}")
        
        # 调用接收回调函数
        if self.receive_callback:
            try:
                self.receive_callback(value)
            except Exception as e:
                logger.error(f"回调函数执行错误: {str(e)}")
    
    def start_advertising(self):
        """
        开始蓝牙广播，等待其他设备连接
        
        Returns:
            bool: 广播是否成功启动
        """
        try:
            if not self.server:
                logger.error("蓝牙服务未初始化")
                return False
            
            logger.info(f"开始蓝牙广播，服务名称: {self.service_name}")
            self.server.start()
            
            # 启动主循环线程
            self._start_mainloop_thread()
            
            logger.info("蓝牙广播已启动，等待设备连接...")
            return True
        except Exception as e:
            logger.error(f"启动广播失败: {str(e)}")
            return False
    
    def stop_advertising(self):
        """
        停止蓝牙广播
        
        Returns:
            bool: 广播是否成功停止
        """
        try:
            if not self.server:
                logger.warning("蓝牙服务未初始化")
                return True
            
            logger.info("停止蓝牙广播")
            self.server.stop()
            
            # 更新连接状态
            self.connected_devices.clear()
            self.is_connected = False
            
            # 停止主循环线程
            self.rx_stop_event.set()
            if self.rx_thread and self.rx_thread.is_alive():
                self.rx_thread.join(2)
            
            logger.info("蓝牙广播已停止")
            return True
        except Exception as e:
            logger.error(f"停止广播失败: {str(e)}")
            return False
    
    def send_data(self, data, device_address=None):
        """
        向已连接的设备发送数据
        
        Args:
            data (str or bytes): 要发送的数据
            device_address (str, optional): 目标设备地址，如果为None则发送给所有连接的设备
        
        Returns:
            bool: 发送是否成功
        """
        try:
            if not self.is_connected or not self.connected_devices:
                logger.error("没有已连接的设备，无法发送数据")
                return False
            
            # 如果数据是字符串，转换为字节
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            
            # 发送数据
            if device_address:
                # 发送给指定设备
                if device_address in self.connected_devices:
                    self._notify_device(device_address, data_bytes)
                    logger.info(f"向设备 {device_address} 发送数据: {data_bytes}")
                else:
                    logger.error(f"设备 {device_address} 未连接")
                    return False
            else:
                # 发送给所有设备
                for addr in self.connected_devices:
                    self._notify_device(addr, data_bytes)
                    logger.info(f"向设备 {addr} 发送数据: {data_bytes}")
            
            return True
        except Exception as e:
            logger.error(f"发送数据失败: {str(e)}")
            return False
    
    def _notify_device(self, device_address, data):
        """
        向指定设备发送通知数据
        
        Args:
            device_address (str): 设备地址
            data (bytes): 要发送的数据
        """
        try:
            # 获取特征
            characteristic = self.server.get_characteristic(self.service_uuid, self.characteristic_uuid)
            
            # 发送通知
            if isinstance(characteristic, BlueZGATTCharacteristic):
                characteristic._value = data
                # 触发通知
                for client in characteristic.descriptors.get('2902', {}).get('Value', {}).get('ClientCharacteristicConfiguration', {}):
                    if client == device_address:
                        characteristic.PropertiesChanged({
                            'Value': data
                        })
        except Exception as e:
            logger.error(f"向设备 {device_address} 发送通知失败: {str(e)}")
    
    def _start_mainloop_thread(self):
        """启动主循环线程"""
        self.rx_stop_event.clear()
        self.rx_thread = threading.Thread(target=self._mainloop_run)
        self.rx_thread.daemon = True
        self.rx_thread.start()
    
    def _mainloop_run(self):
        """
        主循环线程函数
        保持程序运行，直到收到停止信号
        """
        logger.info("启动蓝牙主循环")
        
        # 主循环运行
        while not self.rx_stop_event.is_set():
            time.sleep(0.1)
        
        logger.info("蓝牙主循环已停止")
    
    def set_receive_callback(self, callback):
        """
        设置数据接收回调函数
        
        Args:
            callback (function): 接收数据时调用的函数，参数为接收到的数据
        """
        self.receive_callback = callback
    
    def run_mainloop(self):
        """
        运行蓝牙主循环
        在服务端模式下，此方法会启动广播并保持程序运行
        """
        try:
            if not self.server:
                logger.error("蓝牙服务未初始化")
                return
            
            # 开始广播
            if not self.start_advertising():
                logger.error("启动广播失败")
                return
            
            # 保持主线程运行
            logger.info("蓝牙服务端已启动，按Ctrl+C退出")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("用户中断程序")
        except Exception as e:
            logger.error(f"主循环异常: {str(e)}")
        finally:
            self.stop_advertising()
    
    def quit_mainloop(self):
        """
        退出蓝牙主循环
        """
        self.stop_advertising()
        logger.info("蓝牙主循环已退出")

# 示例用法
if __name__ == '__main__':
    def data_received_handler(data):
        """数据接收处理函数示例"""
        try:
            # 尝试解码接收到的数据
            message = data.decode('utf-8')
            print(f"接收到数据: {message}")
            
            # 可以在这里添加对接收到数据的处理逻辑
            # 例如，如果收到特定指令，可以执行相应操作
            if message.lower() == 'ping':
                bt_manager.send_data('PONG')
        except Exception as e:
            print(f"处理接收到的数据时出错: {str(e)}")
            print(f"原始数据: {data}")
    
    # 创建蓝牙管理器实例
    bt_manager = BluetoothManager()
    
    # 初始化蓝牙服务端
    if not bt_manager.initialize(adapter_name='hci0', service_name='SmileX_Bluetooth_Server'):
        print("蓝牙服务端初始化失败")
        sys.exit(1)
    
    # 设置数据接收回调
    bt_manager.set_receive_callback(data_received_handler)
    
    try:
        # 启动主循环，开始广播并等待连接
        bt_manager.run_mainloop()
    except KeyboardInterrupt:
        print("程序已中断")
    finally:
        # 停止广播并清理资源
        bt_manager.stop_advertising()
        print("蓝牙服务已停止，程序已退出")