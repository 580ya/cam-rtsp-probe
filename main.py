from fastapi import FastAPI

from api.v1.rtsp.probe import router as rtsp_router


app = FastAPI(title="Camera RTSP Probe")
app.include_router(rtsp_router)
