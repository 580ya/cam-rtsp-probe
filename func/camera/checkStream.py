# -*- coding: utf-8 -*-
import asyncio
import os
import cv2


async def check_rtsp_stream(rtsp_url: str) -> bool:
  # ==================== 1. 先尝试 TCP 模式 ====================
  cap = None
  try:
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        "rtsp_transport;tcp|stimeout;5000000"
    )
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    for _ in range(3):
      if cap.isOpened():
        ret, frame = cap.read()
        if ret:
          # TCP 成功读到画面，直接释放并返回 True，绝对不会走到 UDP！
          cap.release()
          return True
      await asyncio.sleep(0.2)

  except Exception as e:
    print(f"TCP check error for {rtsp_url}: {e}")
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

    for _ in range(2):
      if cap.isOpened():
        ret, frame = cap.read()
        if ret:
          cap.release()
          return True
      await asyncio.sleep(0.2)

  except Exception as e:
    print(f"UDP check error for {rtsp_url}: {e}")
  finally:
    if cap is not None:
      try:
        cap.release()
      except Exception:
        pass

  # 两种方式都试过且都失败了
  return False