from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    status: str = Field(default="queued")
    input_path: Optional[str] = None
    theme: Optional[str] = None
    outfit: Optional[str] = None
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
