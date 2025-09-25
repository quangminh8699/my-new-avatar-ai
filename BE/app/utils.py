import os
from dotenv import load_dotenv

def load_env():
    # load .env in project root
    load_dotenv()

def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()
