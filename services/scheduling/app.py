import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

import config
import db
import migrate
from scheduling.router import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("scheduling")


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate.run()
    yield


app = FastAPI(title="TripSync Scheduling", version=config.APP_VERSION, lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        log.info("%s %s %d %.1fms", request.method, request.url.path, status, duration_ms)


@app.get("/health")
def health(response: Response):
    try:
        db.check()
    except Exception as error:
        log.warning("Health check failed: %s", error)
        response.status_code = 503
        return {"status": "error", "db": "unreachable", "version": config.APP_VERSION}
    return {"status": "ok", "db": "ok", "version": config.APP_VERSION}


app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT, access_log=False)
