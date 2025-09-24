import boto3
from io import BytesIO
import uuid
import os

s3 = boto3.client("s3")

def upload_to_s3(image_bytes, key=None):
    if key is None:
        key = str(uuid.uuid4()) + ".png"
    bucket = os.getenv("AWS_BUCKET_NAME")
    s3.upload_fileobj(BytesIO(image_bytes), bucket, key, ExtraArgs={'ContentType': 'image/png'})
    return f"https://{bucket}.s3.amazonaws.com/{key}"
