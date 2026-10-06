# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import quote

from tzlocal import get_localzone

from func.camera.checkStream import check_rtsp_stream


async def get_hik_rtsp(user, password, ip, port=554):
    """获取海康设备的实时主码流地址。

    参数：用户名、密码、设备 IP 和 RTSP 端口。
    返回：第一个可访问的 RTSP 地址，全部失败时返回 False。
    """
    # 对认证信息进行 URL 编码，避免特殊字符破坏 RTSP URL。
    encoded_user = quote(user, safe="")
    encoded_password = quote(password, safe="")
    authority = f"{encoded_user}:{encoded_password}@{ip}:{port}"
    # 按常见海康设备的主码流路径依次尝试。
    urls = [
        f"rtsp://{authority}/Streaming/Channels/1",
        f"rtsp://{authority}/Streaming/Channels/101",
        f"rtsp://{authority}/h265/ch1/main/av_stream",
        f"rtsp://{authority}/h264/ch1/main/av_stream",
    ]

    # 逐个探测候选地址，返回首个能读到视频帧的地址。
    for candidate in urls:
        if await check_rtsp_stream(candidate):
            return candidate

    return False


def _get_replay_window():
    """生成最近一分钟的本地时区回放时间窗口。

    参数：无。
    返回：回放 URL 所需的开始时间和结束时间字符串。
    """
    # 使用项目现有的本地时区约定生成时间窗口。
    local_tz = get_localzone()
    # 获取当前本地时间作为回放结束时间。
    end_time = datetime.now(local_tz)
    # 取当前时间前一分钟作为回放开始时间。
    start_time = end_time - timedelta(minutes=1)
    return (
        start_time.strftime("%Y%m%dT%H%M%SZ"),
        end_time.strftime("%Y%m%dT%H%M%SZ"),
    )


async def get_hik_replay_rtsp(user, password, ip, port=554):
    """获取海康设备最近一分钟的历史回放 RTSP 地址。

    参数：用户名、密码、设备 IP 和 RTSP 端口。
    返回：第一个可访问的回放 RTSP 地址，全部失败时返回 False。
    """
    # 对认证信息进行 URL 编码，兼容包含特殊字符的密码。
    encoded_user = quote(user, safe="")
    encoded_password = quote(password, safe="")
    authority = f"{encoded_user}:{encoded_password}@{ip}:{port}"
    # 生成固定的一分钟回放范围。
    start_time, end_time = _get_replay_window()
    # 海康以 tracks 路径和通道码流编号提供回放。
    urls = [
        f"rtsp://{authority}/Streaming/tracks/101?starttime={start_time}&endtime={end_time}",
        f"rtsp://{authority}/Streaming/tracks/102?starttime={start_time}&endtime={end_time}",
    ]

    # 逐个探测回放候选地址，避免不同型号只支持其中一路码流。
    for candidate in urls:
        if await check_rtsp_stream(candidate):
            return candidate

    return False
