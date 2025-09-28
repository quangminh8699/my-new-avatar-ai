import os
from celery import Celery
from app.ai_agent import generate_avatar_bytes
from app.storage import upload_bytes_to_s3
from app.db import async_session
from app.models import Job
from app.utils import push_update
import asyncio
from datetime import datetime

celery = Celery(__name__, broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

@celery.task(bind=True)
def generate_avatar_task(self, input_path: str, theme: str, outfit: str, job_id: str):
    async def _run():
        from sqlmodel import select
        async with async_session() as session:
            q = select(Job).where(Job.job_id == job_id)
            res = await session.exec(q)
            job = res.one_or_none()
            if job:
                job.status = "processing"
                job.updated_at = datetime.now()
                await session.commit()
        # push realtime update
        push_update(job_id, status="processing")

        try:
            img_bytes = await generate_avatar_bytes(input_path, theme, outfit)
            url = upload_bytes_to_s3(img_bytes, key=f"{job_id}_result.png")

            async with async_session() as session:
                q = select(Job).where(Job.job_id == job_id)
                res = await session.exec(q)
                job = res.one()
                job.status = "done"
                job.result_url = url
                job.updated_at = datetime.now()
                await session.commit()

            push_update(job_id, status="done", url=url)
            return url

        except Exception as e:
            async with async_session() as session:
                q = select(Job).where(Job.job_id == job_id)
                res = await session.exec(q)
                job = res.one_or_none()
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    job.updated_at = datetime.now()
                    await session.commit()

            push_update(job_id, status="failed", error=str(e))
            raise

    return asyncio.get_event_loop().run_until_complete(_run())
