# -*- coding: utf-8 -*-
"""摄像头 RTSP 探测调试日志工具。"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit


LOGGER_NAME = "cam_rtsp_probe"


def get_log_path() -> Path:
    """获取跨平台调试日志路径。

    参数：无。
    返回：调试日志文件路径。
    """
    # 根据操作系统选择用户级日志目录，避免写入安装目录。
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Logs" / "CameraRTSPProbe"
    elif os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        base_dir = base_dir / "CameraRTSPProbe"
    else:
        state_home = os.environ.get("XDG_STATE_HOME")
        base_dir = Path(state_home) if state_home else Path.home() / ".local" / "state"
        base_dir = base_dir / "CameraRTSPProbe"
    # 返回固定名称的滚动日志文件。
    return base_dir / "debug.log"


def describe_rtsp_url(rtsp_url: str | None) -> str:
    """生成不包含用户名和密码的 RTSP 地址描述。

    参数：待描述的 RTSP 地址。
    返回：仅包含主机、端口、路径和查询参数的安全描述。
    """
    # 空地址直接返回占位文本。
    if not rtsp_url:
        return "<empty>"
    try:
        # 解析 URL 后只读取不含认证信息的字段。
        parsed_url = urlsplit(rtsp_url)
        host = parsed_url.hostname or "<no-host>"
        port = f":{parsed_url.port}" if parsed_url.port else ""
        path = parsed_url.path or "/"
        query = f"?{parsed_url.query}" if parsed_url.query else ""
        return f"rtsp://{host}{port}{path}{query}"
    except Exception:
        # URL 格式异常时不输出原始字符串，避免意外泄露认证信息。
        return "<invalid-rtsp-url>"


def configure_logging() -> logging.Logger:
    """初始化应用滚动文件日志并返回日志对象。

    参数：无。
    返回：应用专用日志对象。
    """
    # 获取应用专用 logger，避免修改第三方库的全局日志配置。
    logger = logging.getLogger(LOGGER_NAME)
    # 已经配置过时直接复用，避免重复写入同一条日志。
    if logger.handlers:
        return logger

    # 获取用户级日志文件路径。
    log_path = get_log_path()
    try:
        # 创建日志目录并限制单个日志文件大小。
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        # 使用时间、级别和消息组成易读日志格式。
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        # 记录 DEBUG 级别，便于定位打包环境差异。
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        logger.propagate = False
        logger.info("debug logging started; path=%s", log_path)
    except Exception:
        # 日志目录不可写时不阻塞主程序，只保留空处理器。
        logger.addHandler(logging.NullHandler())
    return logger
