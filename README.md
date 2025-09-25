Giai đoạn 1: Khởi tạo môi trường
--------------------------------
[ ] Tạo dự án Python FastAPI + Celery + Redis
[ ] Cấu hình .env (keys S3, provider API)
[ ] Dockerfile + docker-compose cho API, Worker, Redis, DB

Giai đoạn 2: API cơ bản
------------------------
[ ] /jobs: nhận upload, lưu file tạm, tạo record DB (status=queued)
[ ] /jobs/{id}: trả trạng thái (queued/processing/done/failed + URL)

Giai đoạn 3: Worker xử lý
-------------------------
[ ] Celery task nhận path ảnh/theme/outfit/job_id
[ ] Gọi Agno Agent (app/ai_agent)
[ ] Agent gọi tool ImageGenTool tới provider API sinh ảnh
[ ] Upload ảnh S3, update DB status=done, lưu result_url

Giai đoạn 4: Memory + Logging + Orchestration
---------------------------------------------
[ ] Thêm SQLModel/Postgres lưu metadata job
[ ] Sử dụng Agno memory/tool để lưu style preferences user (nếu muốn)
[ ] Logging, error handling, retry

Giai đoạn 5: Hoàn thiện & tối ưu
-------------------------------
[ ] Validate ảnh upload, giới hạn size
[ ] Triển khai WebSocket nếu muốn realtime
[ ] Monitor chi phí API provider
[ ] Scale worker bằng docker-compose/k8s