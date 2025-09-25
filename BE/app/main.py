import os
import uuid
from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from app.workers import generate_avatar_task
from app.db import init_db, async_session
from app.models import Job
from sqlmodel import select
from app.utils import load_env
from pathlib import Path
from datetime import datetime

load_env()

app = FastAPI(title="Avatar AI (FastAPI + Agno + Celery)")

# ensure DB initialized at startup
@app.on_event("startup")
async def startup():
    await init_db()

@app.post("/jobs")
async def create_job(file: UploadFile, theme: str = Form(...), outfit: str = Form(...)):
    job_uuid = str(uuid.uuid4())
    # save uploaded temporarily to /tmp or project tmp dir
    tmp_dir = Path("/tmp/avatars")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = str(tmp_dir / f"{job_uuid}_{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # create DB record
    async with async_session() as session:
        job = Job(job_id=job_uuid, status="queued", input_path=temp_path, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        session.add(job)
        await session.commit()

    # enqueue celery task
    generate_avatar_task.delay(temp_path, theme, outfit, job_uuid)

    return {"job_id": job_uuid, "status": "queued"}

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    async with async_session() as session:
        q = select(Job).where(Job.job_id == job_id)
        res = await session.exec(q)
        job = res.one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return {
            "job_id": job.job_id,
            "status": job.status,
            "result_url": job.result_url,
            "error": job.error,
            "created_at": job.created_at,
            "updated_at": job.updated_at
        }
