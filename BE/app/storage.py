import boto3
from io import BytesIO
import os
import uuid

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-1")
)

BUCKET = os.getenv("AWS_BUCKET_NAME")

def upload_bytes_to_s3(image_bytes: bytes, key: str = None) -> str:
    if key is None:
        key = f"{uuid.uuid4()}.png"
    s3.upload_fileobj(BytesIO(image_bytes), BUCKET, key, ExtraArgs={"ContentType": "image/png"})
    return f"https://{BUCKET}.s3.amazonaws.com/{key}"
