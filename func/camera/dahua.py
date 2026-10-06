# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import quote

from tzlocal import get_localzone

from func.camera.checkStream import check_rtsp_stream


async def get_dahua_rtsp(user, password, ip, port=554):
    """获取大华设备的实时主码流地址。

    参数：用户名、密码、设备 IP 和 RTSP 端口。
    返回：可访问的实时 RTSP 地址，失败时返回 False。
    """
    # 对认证信息进行 URL 编码，避免特殊字符破坏 RTSP URL。
    encoded_user = quote(user, safe="")
    encoded_password = quote(password, safe="")
    authority = f"{encoded_user}:{encoded_password}@{ip}:{port}"
    # 大华主码流使用 subtype=0。
    url = f"rtsp://{authority}/cam/realmonitor?channel=1&subtype=0"
    # 先验证地址能否实际读取到视频帧。
    ok = await check_rtsp_stream(url)

    if ok is True:
        return url

    return False


def _get_replay_window():
    """生成最近一分钟的大华本地时区回放时间窗口。

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
        start_time.strftime("%Y_%m_%d_%H_%M_%S"),
        end_time.strftime("%Y_%m_%d_%H_%M_%S"),
    )


async def get_dahua_replay_rtsp(user, password, ip, port=554):
    """获取大华设备最近一分钟的历史回放 RTSP 地址。

    参数：用户名、密码、设备 IP 和 RTSP 端口。
    返回：可访问的回放 RTSP 地址，失败时返回 False。
    """
    # 对认证信息进行 URL 编码，兼容包含特殊字符的密码。
    encoded_user = quote(user, safe="")
    encoded_password = quote(password, safe="")
    authority = f"{encoded_user}:{encoded_password}@{ip}:{port}"
    # 生成大华约定格式的最近一分钟时间范围。
    start_time, end_time = _get_replay_window()
    # 依次尝试主码流和子码流，兼容不同设备的录像配置。
    urls = [
        f"rtsp://{authority}/cam/playback?channel=1&subtype=0&starttime={start_time}&endtime={end_time}",
        f"rtsp://{authority}/cam/playback?channel=1&subtype=1&starttime={start_time}&endtime={end_time}",
    ]

    # 只返回能读到视频帧的历史地址。
    for candidate in urls:
        if await check_rtsp_stream(candidate):
            return candidate

    return False
