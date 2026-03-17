# My New Avatar AI

A SaaS application that generates AI-powered avatar images from user portrait photos. Users upload a photo, select a **theme** (style/aesthetic) and an **outfit** (clothing style), and the system produces a personalized avatar while preserving the user's identity.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Technologies](#technologies)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [AWS EC2 Deployment](#aws-ec2-deployment)

---

## What It Does

1. A user uploads a portrait photo and selects a theme + outfit via the web UI.
2. The system returns a `job_id` immediately and queues the generation task.
3. The user's browser opens a WebSocket connection for real-time status updates.
4. A Celery worker picks up the job:
   - **Claude AI** (claude-sonnet-4-6) analyzes the portrait using vision and crafts a detailed, identity-preserving generation prompt.
   - The prompt is sent to an image generation API (Stability AI or Replicate).
   - The result is uploaded to **AWS S3**.
   - The S3 URL is pushed to the client via Redis pub/sub → WebSocket.

---

## Technologies

| Layer | Technology | Role |
|---|---|---|
| Frontend | **Next.js 14** + **Tailwind CSS** | Web UI: upload, status, result display |
| API Server | **FastAPI** + **Uvicorn** | REST endpoints and WebSocket server |
| Background Jobs | **Celery** | Async task queue for image generation |
| Messaging / Broker | **Redis** | Celery broker and pub/sub for real-time updates |
| Database | **MySQL 8.0** + **SQLModel** + **aiomysql** | Job metadata persistence (async ORM) |
| AI Orchestration | **Claude AI** (claude-sonnet-4-6) | Vision analysis + prompt engineering via Anthropic API |
| Image Generation | **Stability AI** / **Replicate** | Actual image synthesis (provider is configurable) |
| Cloud Storage | **AWS S3** + **boto3** | Stores generated avatar images |
| HTTP Client | **httpx** | Async calls to external AI provider APIs |
| Containerization | **Docker** + **Docker Compose** | Runs all services together |
| Deployment | **AWS EC2** | Hosts all containers in production |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│               Next.js Frontend (port 3000)               │
│   Upload form · Theme picker · WebSocket · Result view   │
└───────────────────────────┬──────────────────────────────┘
                            │ HTTP REST + WebSocket
                            ▼
┌──────────────────────────────────────────────────────────┐
│               FastAPI API Server (port 8000)             │
│   POST /jobs · GET /jobs/{id} · WS /ws/jobs/{id}         │
└──────┬───────────────────────────────────────┬───────────┘
       │ enqueue task                          │ subscribe
       ▼                                       ▼
┌─────────────┐                       ┌─────────────────┐
│   Celery    │                       │      Redis      │
│   Worker    │──── publish status ──▶│   pub/sub       │
└──────┬──────┘                       └────────┬────────┘
       │                                       │ push to WS
       ▼                                       ▼
┌───────────────────┐               ┌─────────────────────┐
│  Claude AI        │               │  FastAPI WS Handler │
│  (claude-sonnet)  │               └─────────────────────┘
│  Vision analysis  │
│  + Prompt craft   │
└──────┬────────────┘
       │ rich text prompt
       ▼
┌───────────────────┐     ┌───────────────┐     ┌──────────┐
│  Stability AI /   │     │   MySQL DB    │     │  AWS S3  │
│  Replicate API    │     │  (job state)  │     │  (imgs)  │
└───────────────────┘     └───────────────┘     └──────────┘
```

---

## Project Structure

```
my-new-avatar-ai/
├── FE/                          # Next.js frontend
│   ├── src/app/
│   │   ├── page.tsx             # Main UI: upload, status, result
│   │   ├── layout.tsx           # Root layout + metadata
│   │   └── globals.css          # Tailwind base styles
│   ├── Dockerfile               # Multi-stage Node.js build
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── BE/                          # Python backend
│   ├── app/
│   │   ├── main.py              # FastAPI app: REST + WebSocket
│   │   ├── models.py            # SQLModel Job schema
│   │   ├── db.py                # Async MySQL engine + session
│   │   ├── workers.py           # Celery task: full generation pipeline
│   │   ├── ai_agent.py          # Claude Vision + image generation
│   │   ├── storage.py           # AWS S3 upload helper
│   │   └── utils.py             # Redis pub/sub + file I/O
│   ├── Dockerfile               # Python 3.11 image
│   └── requirements.txt         # Python dependencies
│
├── docker-compose.yml           # All services: frontend, api, worker, db, redis
├── .env                         # Environment variables (API keys, credentials)
└── README.md
```

---

## How It Works

### Avatar Generation Pipeline

```
1. User submits POST /jobs (image + theme + outfit)
   ├─ FastAPI saves image to /tmp/{job_id}_{filename}
   ├─ Creates Job record in MySQL (status = "queued")
   ├─ Enqueues Celery task
   └─ Returns { job_id, status: "queued" }

2. Browser opens WebSocket /ws/jobs/{job_id}
   └─ FastAPI subscribes to Redis channel "jobs_updates"

3. Celery worker executes:
   │
   ├─ a) Update DB → status = "processing"; publish to Redis
   │
   ├─ b) Claude AI Vision Analysis
   │     ├─ Portrait image sent to claude-sonnet-4-6 as base64
   │     ├─ Claude analyzes: facial features, skin tone, hair, expression
   │     └─ Returns a rich, detailed text-to-image generation prompt
   │
   ├─ c) Image Generation (via IMAGE_PROVIDER)
   │     ├─ STABILITY → POST stability.ai SDXL endpoint
   │     └─ REPLICATE → POST replicate.com predictions (polling)
   │
   ├─ d) Upload to AWS S3
   │     └─ Returns https://{bucket}.s3.amazonaws.com/{job_id}_result.png
   │
   └─ e) Update DB → status = "done", result_url = S3 URL
         └─ Publish to Redis → WebSocket → Browser displays avatar

4. On any error:
   ├─ Update DB → status = "failed", error = message
   └─ Publish to Redis → WebSocket → Browser shows error
```

---

## API Reference

### `POST /jobs`

Submit an avatar generation job.

**Request** (multipart/form-data):

| Field | Type | Description |
|---|---|---|
| `file` | file | Portrait photo (JPEG, PNG, WebP) |
| `theme` | string | Style theme (e.g. "Cyberpunk", "Fantasy", "Anime") |
| `outfit` | string | Clothing style (e.g. "leather jacket", "business suit") |

**Response** `200 OK`:
```json
{ "job_id": "550e8400-...", "status": "queued" }
```

---

### `GET /jobs/{job_id}`

Fetch job status and result URL.

**Response** `200 OK`:
```json
{
  "job_id": "550e8400-...",
  "status": "done",
  "url": "https://my-bucket.s3.amazonaws.com/550e8400_result.png",
  "error": null
}
```

Status values: `queued` · `processing` · `done` · `failed`

---

### `WebSocket /ws/jobs/{job_id}`

Real-time job status updates. Messages pushed by the server:

```json
{ "job_id": "...", "status": "processing" }
{ "job_id": "...", "status": "done", "url": "https://..." }
{ "job_id": "...", "status": "failed", "error": "..." }
```

---

## Configuration

All configuration via `.env`:

```env
# Claude AI (Anthropic)
ANTHROPIC_API_KEY=sk-ant-...

# Image Generation Provider: STABILITY | REPLICATE
IMAGE_PROVIDER=STABILITY
STABILITY_API_KEY=sk-...
REPLICATE_API_TOKEN=r8_...

# AWS S3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_BUCKET_NAME=my-avatar-bucket

# Database (MySQL)
DATABASE_URL=mysql+aiomysql://root:rootpassword@db:3306/avatarai
MYSQL_ROOT_PASSWORD=rootpassword
MYSQL_DATABASE=avatarai

# Redis
REDIS_URL=redis://redis:6379/0

# EC2 Deployment (set to your EC2 public IP or domain)
# EC2_HOST=your.ec2.public.ip.or.domain
```

---

## Running the Project

**Prerequisites:** Docker and Docker Compose.

```bash
# 1. Clone and configure
git clone https://github.com/your-org/my-new-avatar-ai.git
cd my-new-avatar-ai

# 2. Fill in your API keys
cp .env .env.local   # edit with real keys
# Required: ANTHROPIC_API_KEY, STABILITY_API_KEY (or REPLICATE_API_TOKEN)
# Required: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET_NAME

# 3. Start all services
docker compose up --build

# Services:
#   frontend → http://localhost:3000
#   api      → http://localhost:8000
#   worker   → Celery background worker
#   db       → MySQL on port 3306
#   redis    → Redis on port 6379
```

**Test the API directly:**

```bash
curl -X POST http://localhost:8000/jobs \
  -F "file=@/path/to/portrait.jpg" \
  -F "theme=Cyberpunk" \
  -F "outfit=leather jacket"

curl http://localhost:8000/jobs/{job_id}
```

---

## AWS EC2 Deployment

```bash
# On your EC2 instance (Amazon Linux 2 / Ubuntu):

# 1. Install Docker
sudo yum update -y
sudo yum install docker -y
sudo service docker start
sudo usermod -aG docker ec2-user
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 2. Clone the repo and configure
git clone https://github.com/your-org/my-new-avatar-ai.git
cd my-new-avatar-ai

# Edit .env with real credentials and set EC2_HOST:
echo "EC2_HOST=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)" >> .env

# 3. Open ports in EC2 Security Group:
#   - 3000 (frontend)
#   - 8000 (API)

# 4. Build and run
docker-compose up --build -d

# 5. View logs
docker-compose logs -f
```

**S3 Bucket policy** — make sure your IAM user has:
- `s3:PutObject` on `arn:aws:s3:::your-bucket-name/*`
- `s3:GetObject` on `arn:aws:s3:::your-bucket-name/*` (for public read)

For public avatar URLs, configure the bucket policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::your-bucket-name/*"
  }]
}
```
