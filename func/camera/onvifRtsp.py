# -*- coding: utf-8 -*-
import asyncio
from onvif import ONVIFCamera
from datetime import datetime, timedelta

import os
import sys
from tzlocal import get_localzone
from func.camera.checkStream import check_rtsp_stream


# 获取当前模块目录，用于开发环境定位项目资源。
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# PyInstaller 环境使用打包根目录，源码环境使用项目根目录。
RESOURCE_ROOT = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(CURRENT_DIR, "..", "..")))
# 固定 ONVIF 所需 WSDL 目录的位置。
WSDL_DIR = os.path.join(RESOURCE_ROOT, "wsdl")


async def check_rtsp_accessible(rtsp_url, timeout=5):
    _check = await check_rtsp_stream(rtsp_url)
    return _check


async def get_capabilities(cam):
    """获取设备支持的服务"""
    try:
        capabilities = cam.devicemgmt.GetCapabilities()
        return capabilities
    except Exception as e:
        return None  # 获取 Capabilities 时发生错误


async def get_live_rtsp(cam):
    """获取实时预览 RTSP 地址（ONVIF 方式，返回纯地址）"""
    try:
        media_service = cam.create_media_service()
        profiles = await asyncio.to_thread(media_service.GetProfiles)
        if not profiles:
            return None  # 未找到任何媒体配置文件

        profile_token = profiles[0].token

        stream_request = media_service.create_type('GetStreamUri')
        stream_request.ProfileToken = profile_token
        stream_request.StreamSetup = {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}}
        stream_uri = await asyncio.to_thread(media_service.GetStreamUri, stream_request)
        rtsp_url = stream_uri.Uri
        return rtsp_url
    except Exception as e:
        return False  # 提取实时预览地址时发生错误


async def get_replay_rtsp_onvif(cam):
    """通过 ONVIF 获取历史回放 RTSP 地址（返回纯地址）"""
    try:
        replay_service = cam.create_replay_service()
        recording_service = cam.create_recording_service()

        recordings = await asyncio.to_thread(recording_service.GetRecordings)
        if not recordings:
            return None  # 未找到任何录像记录

        recording_token = recordings[0].token

        replay_request = replay_service.create_type('GetReplayUri')
        replay_request.RecordingToken = recording_token
        replay_request.StreamSetup = {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}}
        replay_uri = await asyncio.to_thread(replay_service.GetReplayUri, replay_request)
        rtsp_url = replay_uri.Uri
        return rtsp_url
    except Exception as e:
        return False  # 提取 ONVIF 回放地址时发生错误


def get_replay_rtsp_custom(ip, rtsp_port, channel=1, subtype=0):
    """按自定义格式拼接历史回放 RTSP 地址（返回纯地址）"""
    rtsp_url = f"rtsp://{ip}:{rtsp_port}/cam/playback?channel={channel}&subtype={subtype}"
    return rtsp_url


async def extract_rtsp_addresses(ip, port, rtsp_port, username, password):
    """提取实时预览和历史回放 RTSP 地址（返回纯地址）"""
    try:
        cam = ONVIFCamera(ip, port, username, password, wsdl_dir=WSDL_DIR)
    except Exception as e:
        return False, False  # 创建 ONVIFCamera 时发生错误

    # 获取当前时间和前1分钟时间（仅用于检查）
    local_tz = get_localzone()  # 提取本地时区
    now = datetime.now(local_tz)
    start_time = now - timedelta(minutes=1)
    end_time = now

    # 检查支持的服务
    capabilities = await get_capabilities(cam)
    support_replay = capabilities and hasattr(capabilities, 'Replay') and capabilities.Replay is not None

    # 提取实时预览地址
    _live_rtsp = await get_live_rtsp(cam)
    live_check_url = f"rtsp://{username}:{password}@{_live_rtsp[7:]}" if _live_rtsp else None

    if live_check_url and await check_rtsp_accessible(live_check_url):
        live_rtsp = live_check_url
    else:
        live_rtsp = False

    # 提取回放地址
    replay_rtsp = None

    if support_replay:
        _replay_rtsp = await get_replay_rtsp_onvif(cam)
        replay_check_url = f"rtsp://{username}:{password}@{_replay_rtsp[7:]}" if _replay_rtsp else False
    else:
        _replay_rtsp = get_replay_rtsp_custom(ip, rtsp_port)
        replay_check_url = f"rtsp://{username}:{password}@{_replay_rtsp[7:]}&starttime={start_time.strftime('%Y_%m_%d_%H_%M_%S')}&endtime={end_time.strftime('%Y_%m_%d_%H_%M_%S')}"

    if replay_check_url and await check_rtsp_accessible(replay_check_url):
        replay_rtsp = replay_check_url
    else:
        replay_rtsp = False

    return live_rtsp, replay_rtsp


async def main():
    # 摄像头信息
    IP = ""
    PORT = 80  # ONVIF 端口
    RTSP_PORT = 554  # RTSP 端口
    USERNAME = ""
    PASSWORD = ""

    live_rtsp, replay_rtsp = await extract_rtsp_addresses(IP, PORT, RTSP_PORT, USERNAME, PASSWORD)
    print("最终结果：")
    print(f"实时预览 RTSP: {live_rtsp}")
    print(f"历史回放 RTSP: {replay_rtsp}")


async def get_onvif_url(IP, PORT, RTSP_PORT, USERNAME, PASSWORD):
    live_rtsp, replay_rtsp = await extract_rtsp_addresses(IP, PORT, RTSP_PORT, USERNAME, PASSWORD)
    return live_rtsp, replay_rtsp


# 手动调试
if __name__ == "__main__":
    asyncio.run(main())
