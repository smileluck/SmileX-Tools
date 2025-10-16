#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later


import argparse
import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service

import array
from gi.repository import GLib
import sys

from random import randint

mainloop = None

BLUEZ_SERVICE_NAME = "org.bluez"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
ADAPTER_IFACE = "org.bluez.Adapter1"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
GATT_DESC_IFACE = "org.bluez.GattDescriptor1"


LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"


class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotSupported"


class NotPermittedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotPermitted"


class InvalidValueLengthException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.InvalidValueLength"


class FailedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.Failed"


class Application(dbus.service.Object):
    """
    org.bluez.GattApplication1 interface implementation
    """

    def __init__(self, bus):
        self.path = "/"
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)
        # self.add_service(HeartRateService(bus, 0))
        # self.add_service(BatteryService(bus, 1))
        # self.add_service(TestService(bus, 2))
        self.add_service(WIFIService(bus, 0))

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        print("GetManagedObjects")

        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
                descs = chrc.get_descriptors()
                for desc in descs:
                    response[desc.get_path()] = desc.get_properties()

        return response


class Service(dbus.service.Object):
    """
    org.bluez.GattService1 interface implementation
    """

    PATH_BASE = "/org/bluez/example/service"

    def __init__(self, bus, index, uuid, primary):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                "UUID": self.uuid,
                "Primary": self.primary,
                "Characteristics": dbus.Array(
                    self.get_characteristic_paths(), signature="o"
                ),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristic_paths(self):
        result = []
        for chrc in self.characteristics:
            result.append(chrc.get_path())
        return result

    def get_characteristics(self):
        return self.characteristics

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_SERVICE_IFACE]


class Characteristic(dbus.service.Object):
    """
    org.bluez.GattCharacteristic1 interface implementation
    """

    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + "/char" + str(index)
        self.bus = bus
        self.uuid = uuid
        self.service = service
        self.flags = flags
        self.descriptors = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                "Service": self.service.get_path(),
                "UUID": self.uuid,
                "Flags": self.flags,
                "Descriptors": dbus.Array(self.get_descriptor_paths(), signature="o"),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_descriptor(self, descriptor):
        self.descriptors.append(descriptor)

    def get_descriptor_paths(self):
        result = []
        for desc in self.descriptors:
            result.append(desc.get_path())
        return result

    def get_descriptors(self):
        return self.descriptors

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        print("Default ReadValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        print("Default WriteValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self):
        print("Default StartNotify called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self):
        print("Default StopNotify called, returning error")
        raise NotSupportedException()

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class Descriptor(dbus.service.Object):
    """
    org.bluez.GattDescriptor1 interface implementation
    """

    def __init__(self, bus, index, uuid, flags, characteristic):
        self.path = characteristic.path + "/desc" + str(index)
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.chrc = characteristic
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_DESC_IFACE: {
                "Characteristic": self.chrc.get_path(),
                "UUID": self.uuid,
                "Flags": self.flags,
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_DESC_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_DESC_IFACE]

    @dbus.service.method(GATT_DESC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        print("Default ReadValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_DESC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        print("Default WriteValue called, returning error")
        raise NotSupportedException()


class WIFIService(Service):
    """
    WiFi服务，用于接收WiFi账号密码并返回SUCCESS

    """

    WIFI_SVC_UUID = "12345678-1234-5678-1234-56789abcdef7"

    def __init__(self, bus, index):
        Service.__init__(self, bus, index, self.WIFI_SVC_UUID, True)
        self.add_characteristic(WiFiCharacteristic(bus, 0, self))
        self.add_characteristic(WiFiNotifyCharacteristic(bus, 1, self))


class CharacteristicUserDescriptionDescriptor(Descriptor):
    """
    Writable CUD descriptor.

    """

    CUD_UUID = "2901"

    def __init__(self, bus, index, characteristic):
        self.writable = "writable-auxiliaries" in characteristic.flags
        self.value = array.array("B", b"This is a characteristic for testing")
        self.value = self.value.tolist()
        Descriptor.__init__(
            self, bus, index, self.CUD_UUID, ["read", "write"], characteristic
        )

    def ReadValue(self, options):
        return self.value

    def WriteValue(self, value, options):
        if not self.writable:
            raise NotPermittedException()
        self.value = value


class WiFiCharacteristic(Characteristic):
    """
    WiFi特征，用于接收WiFi账号密码并返回SUCCESS

    """

    WIFI_CHRC_UUID = "12345678-1234-5678-1234-56789abcdef8"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self,
            bus,
            index,
            self.WIFI_CHRC_UUID,
            ["read", "write", "writable-auxiliaries"],
            service,
        )
        self.wifi_ssid = ""
        self.wifi_password = ""
        self.last_status = "SUCCESS"
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))

    def ReadValue(self, options):
        """
        读取操作，返回操作状态（SUCCESS或错误信息）

        Args:
            options: 读取选项

        Returns:
            list: 包含状态信息字节的列表
        """
        print(f"WiFiCharacteristic Read: 返回状态 - {self.last_status}")
        return [dbus.Byte(c) for c in self.last_status.encode("utf-8")]

    def WriteValue(self, value, options):
        """
        写入操作，接收WiFi账号密码数据并解析
        数据格式: [SSID长度(1字节)] + [SSID内容] + [密码长度(1字节)] + [密码内容]

        Args:
            value: 写入的值，包含WiFi账号密码
            options: 写入选项
        """
        print(f"WiFiCharacteristic Write: 接收到WiFi数据，长度: {len(value)}字节")

        try:
            # 检查数据长度是否至少包含两个长度字节
            if len(value) < 2:
                raise ValueError("数据长度不足")

            # 解析SSID长度和内容
            ssid_length = value[0]
            if ssid_length <= 0:
                raise ValueError("SSID长度不能为0")

            # 检查是否有足够的数据用于SSID
            if len(value) < ssid_length + 1:
                raise ValueError("SSID数据不完整")

            # 提取SSID（从索引1开始，取ssid_length个字节）
            ssid_bytes = bytes(value[1 : 1 + ssid_length])
            self.wifi_ssid = ssid_bytes.decode("utf-8")

            # 计算密码部分的起始索引
            password_start_index = 1 + ssid_length

            # 检查是否还有足够的数据用于密码长度字节
            if len(value) <= password_start_index:
                raise ValueError("缺少密码长度数据")

            # 解析密码长度和内容
            password_length = value[password_start_index]

            # 检查是否有足够的数据用于密码
            if len(value) < password_start_index + 1 + password_length:
                raise ValueError("密码数据不完整")

            # 提取密码
            password_bytes = bytes(
                value[
                    password_start_index
                    + 1 : password_start_index
                    + 1
                    + password_length
                ]
            )
            self.wifi_password = password_bytes.decode("utf-8")

            # 打印解析结果
            print(f"成功解析WiFi信息:")
            print(f"- SSID: {self.wifi_ssid}")
            # print(f"- 密码: {'*' * len(self.wifi_password)}")  # 不打印明文密码
            print(f"- 密码：{self.wifi_password}")

            # 这里可以添加连接WiFi的逻辑
            # self.connect_to_wifi(self.wifi_ssid, self.wifi_password)

            # 设置状态为成功
            self.last_status = "SUCCESS"

        except UnicodeDecodeError:
            error_msg = "解析失败: 无效的UTF-8编码"
            print(error_msg)
            self.last_status = f"ERROR: {error_msg}"
        except Exception as e:
            error_msg = f"解析失败: {str(e)}"
            print(error_msg)
            self.last_status = f"ERROR: {error_msg}"

    def connect_to_wifi(self, ssid, password):
        """
        连接WiFi的方法（示例实现）

        Args:
            ssid: WiFi名称
            password: WiFi密码
        """
        print(f"尝试连接到WiFi: {ssid}")
        # 这里应该实现实际的WiFi连接逻辑
        # 例如调用系统API或通过其他方式连接WiFi


class WiFiNotifyCharacteristic(Characteristic):
    """
    Fake WiFi Status characteristic. The wifi status is drained by 2 points
    every 5 seconds.

    """

    WIFI_NOTIFY_UUID = "12345678-1234-5678-1234-56789abcdef9"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index, self.WIFI_NOTIFY_UUID, ["read", "notify"], service
        )
        self.current_index = 0
        self.notifying = False
        self.wifi_status = "SUCCESS"
        self.timeout_id = None  # 用于保存定时器ID
        # self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))

    def notify_wifi_status(self):
        if not self.notifying:
            return
        print("Notifying WiFi Status: " + repr(self.wifi_status))
         # 触发PropertiesChanged信号，通知客户端值已更新
         
        
        self.PropertiesChanged(
            GATT_CHRC_IFACE, {"Value": [dbus.Byte(c) for c in self.wifi_status.encode("utf-8")]}, []
        )

    def drain_wifi_status(self):
        print("Draining WiFi Status")
        if not self.notifying:
            return True
        # 示例：模拟状态变化（可替换为实际WiFi连接状态检测逻辑）
        status_list = ["SUCCESS", "CONNECTING", "ERROR: Timeout", "SUCCESS"]
        current_index = status_list.index(self.wifi_status)
        # 循环切换状态
        self.wifi_status = status_list[(current_index + 1) % len(status_list)]
        print("WiFi Status updated: " + repr(self.wifi_status))
        self.notify_wifi_status()  # 更新后触发通知
        return True  # 保持循环


    def ReadValue(self, options):
        print("WiFi Status read: " + repr(self.wifi_status))
        return [dbus.Byte(c) for c in self.wifi_status.encode("utf-8")]

    def StartNotify(self):
        if self.notifying:
            print("Already notifying, nothing to do")
            return
        print("Start notify WiFi Status")
        self.notifying = True
        self.notify_wifi_status()
        
        self.timeout_id = GLib.timeout_add(1000, self.drain_wifi_status)

    def StopNotify(self):
        if not self.notifying:
            print("Not notifying, nothing to do")
            return

        print("Stop notify WiFi Status")

        self.notifying = False
        
        # 取消定时器
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None


def register_app_cb():
    print("GATT application registered")


def register_app_error_cb(error):
    print("Failed to register application: " + str(error))
    mainloop.quit()


def find_adapter(bus, interface):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, "/"), DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()

    for o, props in objects.items():
        if interface in props.keys():
            return o

    return None


class Advertisement(dbus.service.Object):
    PATH_BASE = "/org/bluez/example/advertisement"

    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = None
        self.manufacturer_data = None
        self.solicit_uuids = None
        self.service_data = None
        self.local_name = None
        self.include_tx_power = False
        self.data = None
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties["Type"] = self.ad_type
        if self.service_uuids is not None:
            properties["ServiceUUIDs"] = dbus.Array(self.service_uuids, signature="s")
        if self.solicit_uuids is not None:
            properties["SolicitUUIDs"] = dbus.Array(self.solicit_uuids, signature="s")
        if self.manufacturer_data is not None:
            properties["ManufacturerData"] = dbus.Dictionary(
                self.manufacturer_data, signature="qv"
            )
        if self.service_data is not None:
            properties["ServiceData"] = dbus.Dictionary(
                self.service_data, signature="sv"
            )
        if self.local_name is not None:
            properties["LocalName"] = dbus.String(self.local_name)
        if self.include_tx_power:
            properties["Includes"] = dbus.Array(["tx-power"], signature="s")

        if self.data is not None:
            properties["Data"] = dbus.Dictionary(self.data, signature="yv")
        return {LE_ADVERTISEMENT_IFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service_uuid(self, uuid):
        if not self.service_uuids:
            self.service_uuids = []
        self.service_uuids.append(uuid)

    def add_solicit_uuid(self, uuid):
        if not self.solicit_uuids:
            self.solicit_uuids = []
        self.solicit_uuids.append(uuid)

    def add_manufacturer_data(self, manuf_code, data):
        if not self.manufacturer_data:
            self.manufacturer_data = dbus.Dictionary({}, signature="qv")
        self.manufacturer_data[manuf_code] = dbus.Array(data, signature="y")

    def add_service_data(self, uuid, data):
        if not self.service_data:
            self.service_data = dbus.Dictionary({}, signature="sv")
        self.service_data[uuid] = dbus.Array(data, signature="y")

    def add_local_name(self, name):
        if not self.local_name:
            self.local_name = ""
        self.local_name = dbus.String(name)

    def add_data(self, ad_type, data):
        if not self.data:
            self.data = dbus.Dictionary({}, signature="yv")
        self.data[ad_type] = dbus.Array(data, signature="y")

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        print("GetAll")
        if interface != LE_ADVERTISEMENT_IFACE:
            raise InvalidArgsException()
        print("returning props")
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        print("%s: Released!" % self.path)


class TestAdvertisement(Advertisement):

    def __init__(self, bus, index, device_name):
        Advertisement.__init__(self, bus, index, "peripheral")
        self.add_service_uuid(WIFIService.WIFI_SVC_UUID)
        # self.add_manufacturer_data(0xFFFF, [0x00, 0x01, 0x02, 0x03])
        # self.add_service_data("9999", [0x00, 0x01, 0x02, 0x03, 0x04])
        self.add_local_name(device_name)
        self.include_tx_power = True
        # self.add_data(0x26, [0x01, 0x01, 0x00])


def gatt_service_manager(bus):

    adapter = find_adapter(bus, GATT_MANAGER_IFACE)
    if not adapter:
        print("GattManager1 interface not found")
        return

    app = Application(bus)

    service_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter), GATT_MANAGER_IFACE
    )

    print("Registering GATT application...")

    service_manager.RegisterApplication(
        app.get_path(),
        {},
        reply_handler=register_app_cb,
        error_handler=register_app_error_cb,
    )


def register_ad_cb():
    print("Advertisement registered")


def register_ad_error_cb(error):
    # 打印详细错误信息（包括DBus错误名称和描述）
    error_name = (
        error.get_dbus_name() if hasattr(error, "get_dbus_name") else "UnknownError"
    )
    error_msg = (
        error.get_dbus_message() if hasattr(error, "get_dbus_message") else str(error)
    )
    print(f"广播注册失败:")
    print(f"  错误类型: {error_name}")
    print(f"  错误描述: {error_msg}")
    # 注册失败时退出主循环（避免程序挂起）
    if mainloop is not None:
        mainloop.quit()


def adapter_props(bus, device_name):

    adapter = find_adapter(bus, ADAPTER_IFACE)
    if not adapter:
        print("Adapter1 interface not found")
        return

    # 修改适配器属性
    adapter_props = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter), "org.freedesktop.DBus.Properties"
    )
    adapter_props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))
    adapter_props.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(1))
    adapter_props.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(1))
    adapter_props.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(300))

    # 设置适配器名称（这会更改蓝牙设备本身的名称）
    try:
        adapter_props.Set("org.bluez.Adapter1", "Alias", dbus.String(device_name))
        print(f"蓝牙适配器名称已设置为: {device_name}")
    except Exception as e:
        print(f"设置蓝牙适配器名称时出错: {e}")


def advertise_manager(bus, device_name):

    adapter = find_adapter(bus, ADAPTER_IFACE)
    if not adapter:
        print("Adapter1 interface not found")
        return

    ad_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter), LE_ADVERTISING_MANAGER_IFACE
    )

    test_advertisement = TestAdvertisement(bus, 0, device_name)
    ad_path = test_advertisement.get_path()

    try:
        # 尝试注册广播
        ad_manager.RegisterAdvertisement(
            ad_path,
            {},  # 空配置表示使用默认参数（如信道、间隔）
            reply_handler=register_ad_cb,
            error_handler=register_ad_error_cb,
        )
    except dbus.exceptions.DBusException as e:
        # 若已存在相同路径的广播实例，先注销再重试
        if "org.bluez.Error.AlreadyExists" in str(e):
            print(f"广播实例 {ad_path} 已存在，尝试注销后重新注册...")
            try:
                ad_manager.UnregisterAdvertisement(ad_path)
                print("已注销旧广播实例")
                # 重新注册
                ad_manager.RegisterAdvertisement(
                    ad_path,
                    {},
                    reply_handler=register_ad_cb,
                    error_handler=register_ad_error_cb,
                )
            except Exception as e2:
                print(f"注销旧广播实例失败: {str(e2)}")
        else:
            print(f"广播注册时发生未知错误: {str(e)}")


def main(device_name="Wujie-Ble"):
    global mainloop

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()

    adapter_props(bus, device_name=device_name)

    gatt_service_manager(bus)
    advertise_manager(bus, device_name=device_name)

    mainloop = GLib.MainLoop()

    mainloop.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # 新增--name参数用于指定蓝牙名称
    parser.add_argument(
        "--name",
        default="Wujie-Ble",
        type=str,
        help="自定义蓝牙广播名称 (default: Wujie-Ble)",
    )

    args = parser.parse_args()

    main(args.name)
