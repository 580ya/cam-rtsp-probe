# -*- coding: utf-8 -*-
"""RTSP 地址帧读取验证。"""

import asyncio
import os

import cv2

from func.debug_log import configure_logging, describe_rtsp_url


LOGGER = configure_logging()
_LOGGED_CV_INFO = False


async def check_rtsp_stream(rtsp_url: str) -> bool:
    """使用 TCP/UDP 读取一帧并验证 RTSP 地址。

    参数：待验证的 RTSP 地址。
    返回：成功读取视频帧返回 True，否则返回 False。
    """
    global _LOGGED_CV_INFO
    # 只记录不含用户名和密码的地址描述。
    safe_url = describe_rtsp_url(rtsp_url)
    LOGGER.info("RTSP check started: %s", safe_url)
    if not _LOGGED_CV_INFO:
        # 首次探测记录 OpenCV 的视频后端，定位打包环境差异。
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

    # ==================== 1. 先尝试 TCP 模式 ====================
    cap = None
    try:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;tcp|stimeout;5000000"
        )
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        LOGGER.info("RTSP TCP capture opened=%s", cap.isOpened())

        for attempt in range(3):
            if cap.isOpened():
                ret, frame = cap.read()
                LOGGER.info(
                    "RTSP TCP read attempt=%d ret=%s frame=%s",
                    attempt + 1,
                    ret,
                    frame is not None,
                )
                if ret:
                    # TCP 成功读到画面，直接释放并返回 True。
                    cap.release()
                    LOGGER.info("RTSP TCP check succeeded: %s", safe_url)
                    return True
            await asyncio.sleep(0.2)
    except Exception:
        LOGGER.exception("RTSP TCP check raised an exception: %s", safe_url)
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    # ==================== 2. TCP 失败，再尝试 UDP 模式 ====================
    cap = None
    try:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;udp|stimeout;5000000"
        )
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        LOGGER.info("RTSP UDP capture opened=%s", cap.isOpened())

        for attempt in range(2):
            if cap.isOpened():
                ret, frame = cap.read()
                LOGGER.info(
                    "RTSP UDP read attempt=%d ret=%s frame=%s",
                    attempt + 1,
                    ret,
                    frame is not None,
                )
                if ret:
                    cap.release()
                    LOGGER.info("RTSP UDP check succeeded: %s", safe_url)
                    return True
            await asyncio.sleep(0.2)
    except Exception:
        LOGGER.exception("RTSP UDP check raised an exception: %s", safe_url)
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    # 两种方式都试过且都失败了。
    LOGGER.warning("RTSP check failed for both TCP and UDP: %s", safe_url)
    return False
