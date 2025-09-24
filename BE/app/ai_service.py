import httpx

def call_ai_service(image_path, theme, outfit):
    # Ví dụ gọi API Replicate hoặc StabilityAI
    # Đọc file
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    # Gửi prompt
    prompt = f"Generate a portrait in {theme} style, wearing {outfit}"
    # TODO: thay bằng API thật
    # giả lập trả về ảnh bytes:
    return image_bytes  # trả về ảnh gốc để test
