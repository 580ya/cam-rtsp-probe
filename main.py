from fastapi import FastAPI

from func.debug_log import configure_logging


configure_logging()

from api.v1.rtsp.probe import router as rtsp_router


app = FastAPI(title="Camera RTSP Probe")
app.include_router(rtsp_router)
