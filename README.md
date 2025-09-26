# My New Avatar AI – Workflow

## 📝 Mô tả dự án
Dịch vụ SaaS AI sinh avatar từ ảnh chân dung người dùng, cho phép chọn **theme** (chủ đề) và **outfit** (trang phục), sau đó AI sẽ sinh ra ảnh mới theo yêu cầu.  
Hệ thống sử dụng:
- **FastAPI** làm REST API & WebSocket server
- **Celery + Redis** để xử lý nền
- **Agno Agent** để điều phối prompt và gọi API model AI
- **AI Model Provider** OpenAI để sinh ảnh
- **AWS S3** để lưu ảnh kết quả
- **Database** MySQL để lưu trạng thái job

---

## 🔄 Luồng xử lý với WebSocket
<img width="1560" height="864" alt="image" src="https://github.com/user-attachments/assets/8b854291-0408-47ed-8092-4c2533265c56" />

## 📌 Giải thích từng bước

1. **`POST /jobs (image, theme, outfit)`**  
   - Client upload ảnh + `theme` + `outfit`.  
   - FastAPI sinh `job_id`, lưu file tạm, tạo record DB với `status = queued`.

2. **`enqueueTask`**  
   - FastAPI đẩy task sang Celery để xử lý nền (không block request HTTP).

3. **`generateImage`**  
   - Celery worker nhận task và gọi **Agno Agent** để thực hiện logic sinh ảnh (tạo prompt, quản lý memory nếu cần, chọn tool).

4. **`postPromptAndImage`**  
   - Agno Agent gửi ảnh + prompt tới AI Model Provider (OpenAI).  
   - Provider trả về ảnh kết quả (dạng bytes hoặc URL).

5. **`uploadImageBytes`**  
   - Worker upload ảnh kết quả lên **AWS S3**.
   - S3 trả về `image URL`.

6. **`saveImageUrl`**  
   - Worker cập nhật database: `status = done` và lưu `result_url` (URL ảnh).

7. **`WebSocket /ws/jobs/{job_id}`**  
   - Client mở WebSocket ngay sau khi nhận `job_id` để lắng nghe cập nhật realtime cho job này.

8. **Push update realtime**  
   - Khi Celery worker hoàn tất, hệ thống publish event
   - FastAPI nhận event và **push** qua WebSocket tới client:  
     ```json
     { "job_id": "...", "status": "done", "url": "https://..." }
     ```
   - Client nhận message và hiển thị ảnh — không cần polling.

---

## ⚙️ Công nghệ chính

- **FastAPI** — REST API + WebSocket server  
- **Celery** — xử lý background jobs (generate/upload)  
- **Redis** — broker cho Celery và pub/sub để notify WebSocket server  
- **Agno Agent** — orchestration: prompt engineering, memory, tool calls  
- **AI Model Provider** — nơi thực sự sinh ảnh
- **AWS S3** — lưu trữ ảnh kết quả
- **Database** — lưu job metadata / status / result_url


