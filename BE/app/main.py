from fastapi import FastAPI, UploadFile, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid, os, redis, json, asyncio
from app.workers import generate_avatar_task
from app.models import Job
from app.db import init_db, async_session
from sqlmodel import select


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_redis = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


@app.post("/jobs")
async def create_job(file: UploadFile, theme: str = Form(...), outfit: str = Form(...)):
    job_id = str(uuid.uuid4())
    temp_path = f"/tmp/{job_id}_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    async with async_session() as session:
        job = Job(
            job_id=job_id,
            status="queued",
            input_path=temp_path,
            theme=theme,
            outfit=outfit,
        )
        session.add(job)
        await session.commit()

    generate_avatar_task.delay(temp_path, theme, outfit, job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    async with async_session() as session:
        q = select(Job).where(Job.job_id == job_id)
        res = await session.exec(q)
        job = res.one_or_none()
        if not job:
            return JSONResponse({"error": "not found"}, status_code=404)
        return {"job_id": job.job_id, "status": job.status, "url": job.result_url, "error": job.error}


@app.websocket("/ws/jobs/{job_id}")
async def ws_job_status(websocket: WebSocket, job_id: str):
    await websocket.accept()
    pubsub = _redis.pubsub()
    pubsub.subscribe("jobs_updates")
    try:
        while True:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                if data["job_id"] == job_id:
                    await websocket.send_json(data)
                    if data["status"] in ("done", "failed"):
                        break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    finally:
        pubsub.close()
