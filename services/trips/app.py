from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

import config
import db
from trips import repository
from trips.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    repository.create_tables()
    yield


app = FastAPI(title="TripSync Trips", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
