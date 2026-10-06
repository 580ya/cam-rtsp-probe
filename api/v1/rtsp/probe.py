# -*- coding: utf-8 -*-
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from func.camera.dahua import get_dahua_replay_rtsp, get_dahua_rtsp
from func.camera.hik import get_hik_replay_rtsp, get_hik_rtsp
from func.camera.onvifRtsp import get_onvif_url
from func.debug_log import configure_logging


LOGGER = configure_logging()


router = APIRouter(prefix="/api/v1/rtsp", tags=["RTSP"])


class ProbeRequest(BaseModel):
    ip: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    user: str
    password: str
    brand: Literal[1, 2, 99]


class ProbeResponse(BaseModel):
    brand: Literal[1, 2, 99]
    live_url: str | None
    replay_url: str | None


@router.post("/probe", response_model=ProbeResponse)
async def probe_rtsp(payload: ProbeRequest) -> ProbeResponse:
    """根据品牌探测实时流和最近一分钟历史流。

    参数：包含摄像头地址、认证信息、端口和品牌的请求模型。
    返回：包含实时与历史 RTSP 地址的响应模型。
    """
    LOGGER.info("API probe request: host=%s port=%s brand=%s", payload.ip, payload.port, payload.brand)
    if payload.brand == 1:
        # 海康同时探测实时流和 tracks 回放流。
        live_url = await get_hik_rtsp(
            payload.user, payload.password, payload.ip, payload.port
        )
        replay_url = await get_hik_replay_rtsp(
            payload.user, payload.password, payload.ip, payload.port
        )
    elif payload.brand == 2:
        # 大华同时探测实时流和 cam/playback 回放流。
        live_url = await get_dahua_rtsp(
            payload.user, payload.password, payload.ip, payload.port
        )
        replay_url = await get_dahua_replay_rtsp(
            payload.user, payload.password, payload.ip, payload.port
        )
    else:
        # ONVIF 继续复用现有实现，品牌值保留为 99。
        live_url, replay_url = await get_onvif_url(
            payload.ip,
            payload.port,
            554,
            payload.user,
            payload.password,
        )

    LOGGER.info("API probe result: live=%s replay=%s", bool(live_url), bool(replay_url))
    return ProbeResponse(
        brand=payload.brand,
        live_url=live_url or None,
        replay_url=replay_url or None,
    )
