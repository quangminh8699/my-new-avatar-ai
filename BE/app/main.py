from fastapi import FastAPI, UploadFile, Form, BackgroundTasks
from fastapi.responses import JSONResponse
import uuid
from .workers import generate_avatar_task

app = FastAPI()

@app.post("/jobs")
async def create_job(file: UploadFile, theme: str = Form(...), outfit: str = Form(...)):
    job_id = str(uuid.uuid4())
    # Lưu file tạm vào disk/S3 (ở đây mình bỏ qua)
    temp_path = f"/tmp/{job_id}_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    # enqueue Celery job
    generate_avatar_task.delay(temp_path, theme, outfit, job_id)
    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    # truy vấn DB hoặc cache; ở đây giả lập
    # TODO: implement DB lookup
    return {"job_id": job_id, "status": "processing"}
