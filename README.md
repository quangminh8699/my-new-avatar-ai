# My New Avatar AI

A SaaS application that generates AI-powered avatar images from user portrait photos. Users upload a photo, select a **theme** (style/aesthetic) and an **outfit** (clothing style), and the system produces a new personalized avatar while preserving the user's identity.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Technologies](#technologies)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)
- [Data Model](#data-model)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)

---

## What It Does

1. A user submits a portrait photo along with a chosen theme and outfit via a REST API.
2. The system returns a `job_id` immediately and queues the generation task in the background.
3. The user opens a WebSocket connection to receive real-time status updates.
4. A Celery worker picks up the job, uses an AI agent to generate the avatar image, uploads the result to AWS S3, and pushes the final URL to the client through Redis pub/sub and WebSocket — no polling required.

---

## Technologies

| Layer | Technology | Role |
|---|---|---|
| API Server | **FastAPI** + **Uvicorn** | REST endpoints and WebSocket server |
| Background Jobs | **Celery** | Async task queue for image generation |
| Messaging / Broker | **Redis** | Celery broker and pub/sub for real-time updates |
| Database | **MySQL 8.0** + **SQLModel** + **aiomysql** | Job metadata persistence (async ORM) |
| AI Orchestration | **Agno** | Agent framework: prompt engineering, tool calls, memory |
| Image Generation | **OpenAI API** / **Replicate API** / **Stability AI API** | Actual image synthesis (provider is configurable) |
| Cloud Storage | **AWS S3** + **boto3** | Stores generated avatar images |
| HTTP Client | **httpx** | Async calls to external AI provider APIs |
| File Uploads | **python-multipart** | Parses multipart form data for image uploads |
| Containerization | **Docker** + **Docker Compose** | Runs all services together |

---

## Architecture

The system is split into four independent services orchestrated by Docker Compose:

```
┌──────────────────────────────────────────────────────┐
│                     Client                           │
│         (HTTP REST + WebSocket)                      │
└───────────────────┬──────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│               FastAPI API Server                     │
│   POST /jobs · GET /jobs/{id} · WS /ws/jobs/{id}     │
└──────┬───────────────────────────────────┬───────────┘
       │ enqueue task                      │ subscribe to updates
       ▼                                   ▼
┌─────────────┐                   ┌─────────────────┐
│   Celery    │                   │      Redis      │
│   Worker    │──publish status──▶│   pub/sub       │
└──────┬──────┘                   └────────┬────────┘
       │                                   │ push to WS client
       ▼                                   ▼
┌─────────────┐                   ┌─────────────────┐
│  Agno Agent │                   │  FastAPI WS     │
│ (ImageGen)  │                   │  Handler        │
└──────┬──────┘                   └─────────────────┘
       │
       ├──▶ OpenAI / Replicate / Stability AI
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   AWS S3    │     │   MySQL DB  │
│ (store img) │     │ (job state) │
└─────────────┘     └─────────────┘
```

**Key design decisions:**

- **Non-blocking API**: The `POST /jobs` endpoint returns immediately with a `job_id`; heavy processing runs entirely in the background via Celery.
- **Real-time updates via Redis pub/sub**: The Celery worker publishes status events to Redis. The FastAPI WebSocket handler subscribes to the `jobs_updates` channel and forwards matching events to the connected client.
- **Pluggable image provider**: The `IMAGE_PROVIDER` environment variable selects between OpenAI, Replicate, or Stability AI without code changes.
- **Async database access**: `aiomysql` and SQLModel's async engine allow non-blocking database operations inside FastAPI's async event loop.

---

## Project Structure

```
my-new-avatar-ai/
├── BE/app/
│   ├── main.py          # FastAPI app: REST endpoints + WebSocket handler
│   ├── models.py        # SQLModel schema (Job table)
│   ├── db.py            # Async database engine and session setup
│   ├── workers.py       # Celery task: orchestrates the full generation pipeline
│   ├── ai_agent.py      # Agno agent + ImageGenTool (calls AI provider APIs)
│   ├── storage.py       # AWS S3 upload helper
│   └── utils.py         # Redis pub/sub helpers and file I/O utilities
├── docker-compose.yml   # Runs API, Worker, MySQL, Redis as containers
├── Dockerfile           # Python 3.11 image for API and Worker services
├── requirements.txt     # Python dependencies
├── sequence-diagram.plantuml  # UML sequence diagram of the full workflow
└── .env                 # Environment variables (API keys, DB credentials)
```

---

## How It Works

### Step-by-step flow

```
1. Client sends POST /jobs
   ├─ Uploads image file + theme + outfit form fields
   ├─ FastAPI generates a UUID job_id
   ├─ Saves image to /tmp/{job_id}_{filename}
   ├─ Creates a Job record in MySQL with status = "queued"
   ├─ Enqueues generate_avatar_task(temp_path, theme, outfit, job_id) in Celery
   └─ Returns { "job_id": "...", "status": "queued" }

2. Client opens WebSocket /ws/jobs/{job_id}
   └─ FastAPI subscribes to Redis channel "jobs_updates"
      and listens for messages matching the job_id

3. Celery worker picks up the task
   │
   ├─ a) Update status → "processing"
   │     Publishes to Redis: { "job_id": "...", "status": "processing" }
   │
   ├─ b) Generate avatar image
   │     ├─ Reads input image bytes from temp file
   │     ├─ Builds prompt:
   │     │   "Create a photorealistic portrait using reference image.
   │     │    Style: {theme}. Clothing: {outfit}. High resolution..."
   │     ├─ Creates Agno Agent with ImageGenTool
   │     ├─ Agent calls ImageGenTool._call_provider() which routes to:
   │     │   ├─ REPLICATE  → POST api.replicate.com/v1/predictions
   │     │   ├─ STABILITY  → POST api.stability.ai/.../text-to-image
   │     │   └─ OPENAI     → POST api.openai.com/v1/images/generations
   │     └─ Returns image bytes
   │
   ├─ c) Upload to AWS S3
   │     ├─ boto3 uploads PNG to S3 bucket
   │     └─ Returns "https://{bucket}.s3.amazonaws.com/{job_id}_result.png"
   │
   └─ d) Save result
         ├─ Updates Job record: status = "done", result_url = S3 URL
         └─ Publishes to Redis: { "job_id": "...", "status": "done", "url": "..." }

4. FastAPI WebSocket handler receives Redis message
   └─ Sends to client: { "job_id": "...", "status": "done", "url": "..." }

5. On error at any step
   ├─ Updates Job: status = "failed", error = exception message
   └─ Publishes to Redis: { "job_id": "...", "status": "failed", "error": "..." }
```

### Sequence Diagram

```
Client        FastAPI       MySQL      Celery Worker   Agno Agent   AI Provider   S3      Redis
  |               |           |              |               |            |         |        |
  |--POST /jobs-->|           |              |               |            |         |        |
  |               |--INSERT-->|              |               |            |         |        |
  |               |--enqueue task----------->|               |            |         |        |
  |<--{job_id}----|           |              |               |            |         |        |
  |               |           |              |               |            |         |        |
  |--WS connect-->|           |              |               |            |         |        |
  |               |<-----------subscribe to Redis pub/sub---------------------------->|      |
  |               |           |              |               |            |         |        |
  |               |           |      status=processing       |            |         |        |
  |               |           |              |--publish--------------------------------------------->|
  |<--{processing}|<---------------------------------------------------------receive--|        |
  |               |           |              |               |            |         |        |
  |               |           |              |--generate---->|            |         |        |
  |               |           |              |               |--API call-->|         |        |
  |               |           |              |               |<--image bytes---------|        |
  |               |           |              |<--img bytes---|            |         |        |
  |               |           |              |                             |--upload->|       |
  |               |           |              |<-----------------------url--|         |        |
  |               |           |              |               |            |         |        |
  |               |           |      status=done, url        |            |         |        |
  |               |           |<--UPDATE-----|               |            |         |        |
  |               |           |              |--publish--------------------------------------------->|
  |<--{done, url}-|<---------------------------------------------------------receive--|        |
```

---

## API Reference

### `POST /jobs`

Submit an avatar generation job.

**Request** (multipart/form-data):

| Field | Type | Description |
|---|---|---|
| `image` | file | Portrait photo (JPEG, PNG, etc.) |
| `theme` | string | Style/aesthetic theme (e.g., "cyberpunk", "fantasy") |
| `outfit` | string | Clothing style (e.g., "suit", "casual") |

**Response** `200 OK`:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

---

### `GET /jobs/{job_id}`

Fetch the current status and result of a job.

**Response** `200 OK`:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "url": "https://my-bucket.s3.amazonaws.com/550e8400_result.png",
  "error": null
}
```

Possible `status` values: `queued` · `processing` · `done` · `failed`

---

### `WebSocket /ws/jobs/{job_id}`

Open a WebSocket connection to receive real-time status updates for a job. Messages are JSON objects pushed by the server whenever the job status changes.

**Example messages received:**

```json
{ "job_id": "...", "status": "processing" }
{ "job_id": "...", "status": "done", "url": "https://..." }
{ "job_id": "...", "status": "failed", "error": "..." }
```

---

## Data Model

**`Job` table (MySQL)**:

| Column | Type | Description |
|---|---|---|
| `id` | int (PK) | Auto-increment primary key |
| `job_id` | varchar (unique) | UUID identifying the job |
| `status` | varchar | `queued` / `processing` / `done` / `failed` |
| `input_path` | varchar | Temporary file path of the uploaded image |
| `theme` | varchar | Theme parameter |
| `outfit` | varchar | Outfit parameter |
| `result_url` | varchar | S3 URL of the generated image |
| `error` | varchar | Error message if the job failed |
| `created_at` | datetime | Job creation timestamp |
| `updated_at` | datetime | Last update timestamp |

---

## Configuration

All configuration is provided via environment variables (`.env` file):

```env
# Database
DATABASE_URL=mysql+aiomysql://root:password@db:3306/my_new_avatar_ai

# Redis
REDIS_URL=redis://redis:6379/0

# AI Provider (choose one: OPENAI, REPLICATE, STABILITY)
IMAGE_PROVIDER=OPENAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ID=gpt-4o
REPLICATE_API_TOKEN=r8_...
STABILITY_API_KEY=sk-...

# AWS S3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_BUCKET_NAME=my-avatar-bucket
```

---

## Running the Project

**Prerequisites:** Docker and Docker Compose installed.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/my-new-avatar-ai.git
cd my-new-avatar-ai

# 2. Create and configure environment variables
cp .env.example .env
# Edit .env with your API keys and credentials

# 3. Start all services
docker compose up --build

# Services started:
#   api    → http://localhost:8000
#   worker → Celery background worker
#   db     → MySQL on port 3306
#   redis  → Redis on port 6379
```

**Test the API:**

```bash
# Submit a job
curl -X POST http://localhost:8000/jobs \
  -F "image=@/path/to/portrait.jpg" \
  -F "theme=cyberpunk" \
  -F "outfit=leather jacket"

# Check job status
curl http://localhost:8000/jobs/{job_id}
```
