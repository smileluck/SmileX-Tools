#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AP模式Wi-Fi配置FastAPI转发器

此脚本实现了一个FastAPI应用，作为sta_wifi_config.py的转发器，提供RESTful API接口来控制Wi-Fi配置功能。

作者: SmileX
版本: 1.0
日期: 2024-07-21
"""
import os
import sys
import json
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 添加当前目录到Python路径，以便导入sta_wifi_config模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入sta_wifi_config模块中的函数
from sta_wifi_config import (
    get_wifi_interfaces,
    start_ap_mode,
    start_web_server,
    save_wifi_config,
    load_wifi_config,
    connect_to_wifi,
    switch_to_sta_mode,
    check_wifi_connection,
    clear_nmcli_connections,
    DEFAULT_AP_SSID,
    DEFAULT_AP_PASSWORD,
    DEFAULT_AP_INTERFACE,
    DEFAULT_AP_IP,
    DEFAULT_AP_PORT,
    CONFIG_FILE
)

# 创建FastAPI应用实例
app = FastAPI(title="AP模式Wi-Fi配置转发器",
              description="提供RESTful API接口来控制Wi-Fi配置功能",
              version="1.0")

# 添加CORS中间件，允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定义请求模型
class WifiConfig(BaseModel):
    ssid: str
    password: str

class ApConfig(BaseModel):
    ssid: str = DEFAULT_AP_SSID
    password: str = DEFAULT_AP_PASSWORD
    interface: str = DEFAULT_AP_INTERFACE

class ConnectWifiRequest(BaseModel):
    ssid: str
    password: str
    interface: str = DEFAULT_AP_INTERFACE
    max_retries: int = 3

@app.get("/", tags=["根路径"])
async def read_root():
    """
    根路径，返回API信息
    
    返回:
        dict: API信息
    """
    return {
        "api_name": "AP模式Wi-Fi配置转发器",
        "version": "1.0",
        "description": "提供RESTful API接口来控制Wi-Fi配置功能"
    }

@app.get("/wifi/interfaces", tags=["无线接口管理"])
async def get_wifi_interfaces_api():
    """
    获取系统上所有的无线网卡接口
    
    返回:
        dict: 包含无线网卡接口列表的响应
    """
    try:
        interfaces = get_wifi_interfaces()
        return {
            "status": "success",
            "data": {
                "interfaces": interfaces,
                "count": len(interfaces)
            },
            "message": f"成功获取了{len(interfaces)}个无线网卡接口"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取无线网卡接口时出错: {str(e)}")

@app.post("/wifi/ap/start", tags=["AP模式管理"])
async def start_ap_mode_api(config: ApConfig = Body(...)):
    """
    启动AP模式，创建Wi-Fi热点
    
    参数:
        config: AP配置信息，包含ssid、password和interface
    
    返回:
        dict: 操作结果响应
    """
    try:
        success, ap_process = start_ap_mode(config.ssid, config.password, config.interface)
        if success:
            return {
                "status": "success",
                "data": {
                    "ssid": config.ssid,
                    "interface": config.interface
                },
                "message": f"AP模式启动成功: {config.ssid}"
            }
        else:
            raise HTTPException(status_code=500, detail="AP模式启动失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置AP模式时出错: {str(e)}")

@app.post("/wifi/ap/stop", tags=["AP模式管理"])
async def stop_ap_mode_api(interface: str = Query(DEFAULT_AP_INTERFACE)):
    """
    停止AP模式，切换到STA模式
    
    参数:
        interface: 无线网卡接口名称
    
    返回:
        dict: 操作结果响应
    """
    try:
        switch_to_sta_mode(interface)
        return {
            "status": "success",
            "data": {
                "interface": interface
            },
            "message": "已切换到STA模式"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换到STA模式时出错: {str(e)}")

@app.post("/wifi/connect", tags=["Wi-Fi连接管理"])
async def connect_wifi_api(request: ConnectWifiRequest = Body(...)):
    """
    连接到指定的Wi-Fi网络
    
    参数:
        request: 连接请求信息，包含ssid、password、interface和max_retries
    
    返回:
        dict: 连接结果响应
    """
    try:
        success = connect_to_wifi(
            request.ssid, 
            request.password, 
            request.interface, 
            request.max_retries
        )
        if success:
            return {
                "status": "success",
                "data": {
                    "ssid": request.ssid,
                    "interface": request.interface
                },
                "message": f"成功连接到Wi-Fi: {request.ssid}"
            }
        else:
            raise HTTPException(status_code=500, detail=f"连接Wi-Fi {request.ssid}失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接Wi-Fi时出错: {str(e)}")

@app.get("/wifi/status", tags=["Wi-Fi状态管理"])
async def check_wifi_status_api():
    """
    检查Wi-Fi连接状态
    
    返回:
        dict: Wi-Fi连接状态响应
    """
    try:
        is_connected = check_wifi_connection()
        return {
            "status": "success",
            "data": {
                "connected": is_connected
            },
            "message": "Wi-Fi已连接" if is_connected else "Wi-Fi未连接"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查Wi-Fi连接状态时出错: {str(e)}")

@app.post("/wifi/config/save", tags=["Wi-Fi配置管理"])
async def save_wifi_config_api(config: WifiConfig = Body(...)):
    """
    保存Wi-Fi配置到文件
    
    参数:
        config: Wi-Fi配置信息，包含ssid和password
    
    返回:
        dict: 保存结果响应
    """
    try:
        save_wifi_config(config.ssid, config.password)
        return {
            "status": "success",
            "data": {
                "ssid": config.ssid,
                "config_file": CONFIG_FILE
            },
            "message": f"Wi-Fi配置已保存到 {CONFIG_FILE}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存Wi-Fi配置时出错: {str(e)}")

@app.get("/wifi/config/load", tags=["Wi-Fi配置管理"])
async def load_wifi_config_api():
    """
    从文件加载Wi-Fi配置
    
    返回:
        dict: 包含加载的配置信息的响应
    """
    try:
        config = load_wifi_config()
        if config:
            # 不要返回密码的完整内容，只返回部分用于验证
            safe_config = config.copy()
            if 'password' in safe_config:
                safe_config['password'] = '********'  # 隐藏密码
            return {
                "status": "success",
                "data": {
                    "config": safe_config,
                    "config_file": CONFIG_FILE
                },
                "message": f"成功加载Wi-Fi配置"
            }
        else:
            return {
                "status": "success",
                "data": {
                    "config": None,
                    "config_file": CONFIG_FILE
                },
                "message": "未找到Wi-Fi配置文件"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载Wi-Fi配置时出错: {str(e)}")

@app.post("/wifi/connections/clear", tags=["Wi-Fi连接管理"])
async def clear_wifi_connections_api():
    """
    清空网络连接历史
    
    返回:
        dict: 操作结果响应
    """
    try:
        success = clear_nmcli_connections()
        if success:
            return {
                "status": "success",
                "message": "已清空网络连接历史"
            }
        else:
            raise HTTPException(status_code=500, detail="清空网络连接历史失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空网络连接历史时出错: {str(e)}")

@app.get("/wifi/defaults", tags=["默认配置"])
async def get_default_config_api():
    """
    获取默认配置信息
    
    返回:
        dict: 默认配置信息响应
    """
    return {
        "status": "success",
        "data": {
            "default_ap_ssid": DEFAULT_AP_SSID,
            "default_ap_password": "********",  # 隐藏密码
            "default_ap_interface": DEFAULT_AP_INTERFACE,
            "default_ap_ip": DEFAULT_AP_IP,
            "default_ap_port": DEFAULT_AP_PORT,
            "config_file": CONFIG_FILE
        },
        "message": "成功获取默认配置信息"
    }

@app.get("/docs/openapi.json", include_in_schema=False)
async def get_openapi_json():
    """
    获取OpenAPI规范JSON
    
    返回:
        dict: OpenAPI规范
    """
    return app.openapi()

def main():
    """
    主函数，启动FastAPI服务器
    """
    # 检查是否以root权限运行
    if os.geteuid() != 0:
        print("错误: 此脚本需要以root权限运行")
        print("请使用 sudo python ap_wifi_config.py 命令运行")
        sys.exit(1)
    
    # 打印启动信息
    print(f"AP模式Wi-Fi配置FastAPI转发器已启动")
    print(f"访问 http://{DEFAULT_AP_IP}:{DEFAULT_AP_PORT}/docs 查看API文档")
    
    # 启动uvicorn服务器
    uvicorn.run(
        "ap_wifi_config:app",
        host=DEFAULT_AP_IP,
        port=DEFAULT_AP_PORT,
        reload=False,  # 生产环境中关闭自动重载
        workers=1     # 单工作进程
    )

if __name__ == "__main__":
    main()