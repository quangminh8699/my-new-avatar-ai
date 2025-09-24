# Base image Python
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy requirements trước để cache layer
COPY requirements.txt .

# Cài đặt thư viện
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Expose port cho FastAPI
EXPOSE 8000

# Lệnh mặc định: chạy FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]