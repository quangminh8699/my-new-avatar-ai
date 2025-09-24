from celery import Celery
from .ai_service import call_ai_service
from .storage import upload_to_s3

celery = Celery(__name__, broker="redis://localhost:6379/0")

@celery.task
def generate_avatar_task(temp_path, theme, outfit, job_id):
    # Gọi AI API sinh ảnh
    img_bytes = call_ai_service(temp_path, theme, outfit)
    # Lưu ảnh kết quả lên S3
    url = upload_to_s3(img_bytes, f"{job_id}_result.png")
    # Cập nhật DB trạng thái (processing -> done)
    print("Job done", job_id, url)
    return url
