# -*- coding: utf-8 -*-
"""RTSP 地址帧读取验证。"""

import asyncio
import os

import av
import cv2

from func.debug_log import configure_logging, describe_rtsp_url


LOGGER = configure_logging()
_LOGGED_CV_INFO = False
_LOGGED_AV_INFO = False


def _read_first_frame_pyav(rtsp_url: str, transport: str) -> bool:
    """使用 PyAV/FFmpeg 读取 RTSP 首帧。

    参数：RTSP 地址和传输协议（tcp 或 udp）。
    返回：成功读取视频帧返回 True，否则返回 False。
    """
    # 传递 RTSP 传输协议和 FFmpeg 网络超时，避免连接永久阻塞。
    options = {
        "rtsp_transport": transport,
        "stimeout": "5000000",
    }
    # 创建 FFmpeg 容器连接。
    container = av.open(rtsp_url, mode="r", options=options, timeout=5.0)
    try:
        # 只解码第一个视频流的第一帧即可完成可访问性验证。
        for frame in container.decode(video=0):
            return frame is not None
    finally:
        # 无论成功或异常都关闭 FFmpeg 容器。
        container.close()
    return False


def _read_first_frame_cv2(rtsp_url: str, transport: str) -> bool:
    """使用 OpenCV 读取 RTSP 首帧作为回退方案。

    参数：RTSP 地址和传输协议（tcp 或 udp）。
    返回：成功读取视频帧返回 True，否则返回 False。
    """
    # 配置 OpenCV FFmpeg 后端的传输协议和网络超时。
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        f"rtsp_transport;{transport}|stimeout;5000000"
    )
    # 强制使用 OpenCV FFmpeg 后端，兼容已有 Linux/Windows 环境。
    capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    try:
        # 记录 OpenCV 是否成功创建捕获对象。
        LOGGER.info("OpenCV %s capture opened=%s", transport.upper(), capture.isOpened())
        for attempt in range(3 if transport == "tcp" else 2):
            if capture.isOpened():
                ret, frame = capture.read()
                LOGGER.info(
                    "OpenCV %s read attempt=%d ret=%s frame=%s",
                    transport.upper(),
                    attempt + 1,
                    ret,
                    frame is not None,
                )
                if ret:
                    return True
        return False
    finally:
        # 释放 OpenCV 捕获对象。
        capture.release()


async def check_rtsp_stream(rtsp_url: str) -> bool:
    """使用 PyAV/FFmpeg 和 OpenCV 读取一帧验证 RTSP 地址。

    参数：待验证的 RTSP 地址。
    返回：成功读取视频帧返回 True，否则返回 False。
    """
    global _LOGGED_CV_INFO, _LOGGED_AV_INFO
    # 只记录不含用户名和密码的地址描述。
    safe_url = describe_rtsp_url(rtsp_url)
    LOGGER.info("RTSP check started: %s", safe_url)

    if not _LOGGED_AV_INFO:
        # 首次探测记录 PyAV 和 FFmpeg 版本，定位打包环境差异。
        try:
            LOGGER.info(
                "PyAV version=%s; FFmpeg libraries=%s",
                av.__version__,
                av.library_versions,
            )
        except Exception:
            LOGGER.exception("failed to read PyAV build information")
        _LOGGED_AV_INFO = True

    # 优先使用 PyAV 自带的 FFmpeg，macOS 不依赖 OpenCV 的 FFmpeg 后端。
    for transport in ("tcp", "udp"):
        try:
            LOGGER.info("PyAV %s check started: %s", transport.upper(), safe_url)
            succeeded = await asyncio.to_thread(
                _read_first_frame_pyav,
                rtsp_url,
                transport,
            )
            LOGGER.info(
                "PyAV %s check result=%s: %s",
                transport.upper(),
                succeeded,
                safe_url,
            )
            if succeeded:
                LOGGER.info("RTSP PyAV check succeeded: %s", safe_url)
                return True
        except Exception:
            LOGGER.exception(
                "PyAV %s check failed: %s",
                transport.upper(),
                safe_url,
            )

    if not _LOGGED_CV_INFO:
        # PyAV 失败时记录 OpenCV 的视频后端，便于判断回退能力。
        try:
            build_info = cv2.getBuildInformation()
            video_io_start = build_info.find("Video I/O:")
            video_io_end = build_info.find("\n\n", video_io_start)
            video_io_info = (
                build_info[video_io_start:video_io_end]
                if video_io_start >= 0
                else "<missing>"
            )
            LOGGER.info(
                "OpenCV version=%s; video backends:\n%s",
                cv2.__version__,
                video_io_info,
            )
        except Exception:
            LOGGER.exception("failed to read OpenCV build information")
        _LOGGED_CV_INFO = True

    # PyAV 失败后保留 OpenCV 回退，避免影响已有 Linux/Windows 行为。
    for transport in ("tcp", "udp"):
        try:
            succeeded = await asyncio.to_thread(
                _read_first_frame_cv2,
                rtsp_url,
                transport,
            )
            if succeeded:
                LOGGER.info("RTSP OpenCV fallback succeeded: %s", safe_url)
                return True
        except Exception:
            LOGGER.exception(
                "OpenCV %s fallback failed: %s",
                transport.upper(),
                safe_url,
            )

    # 两种 FFmpeg/视频后端都失败。
    LOGGER.warning("RTSP check failed with PyAV and OpenCV: %s", safe_url)
    return False
