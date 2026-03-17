import os
import asyncio
import base64
import httpx
import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _analyze_portrait_with_claude(ref_bytes: bytes, media_type: str, theme: str, outfit: str) -> str:
    """Use Claude Vision to analyze the portrait and generate a detailed image generation prompt."""
    client = _get_client()
    ref_b64 = base64.standard_b64encode(ref_bytes).decode("utf-8")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": ref_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Analyze this portrait photo and write a detailed text-to-image generation prompt "
                            f"for an AI avatar. Theme/style: {theme}. Outfit/clothing: {outfit}. "
                            "Describe the subject's facial structure, skin tone, hair color and style, eye color, "
                            "and expression. Then craft a complete generation prompt that preserves the person's "
                            "identity while applying the requested style. Include: photorealistic quality, "
                            "professional portrait lighting, high resolution 8K, sharp focus, no watermark. "
                            "Return ONLY the prompt text, no explanations or preamble."
                        ),
                    },
                ],
            }
        ],
    )

    return message.content[0].text.strip()


async def _generate_with_stability(prompt: str) -> bytes:
    token = os.getenv("STABILITY_API_KEY")
    async with httpx.AsyncClient(timeout=120) as client:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "text_prompts": [
                {"text": prompt, "weight": 1.0},
                {"text": "blurry, low quality, watermark, deformed, ugly, distorted face", "weight": -1.0},
            ],
            "cfg_scale": 7,
            "height": 1024,
            "width": 1024,
            "samples": 1,
            "steps": 30,
        }
        r = await client.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            headers=headers,
            json=payload,
        )
        r.raise_for_status()
        j = r.json()
        return base64.b64decode(j["artifacts"][0]["base64"])


async def _generate_with_replicate(prompt: str) -> bytes:
    token = os.getenv("REPLICATE_API_TOKEN")
    async with httpx.AsyncClient(timeout=180) as client:
        headers = {"Authorization": f"Token {token}"}
        payload = {
            "version": "stability-ai/sdxl:39ed52f2319f9d66ef375c2d49c12dfb39df33da89e10c8d757b10bfd1b9cf87",
            "input": {
                "prompt": prompt,
                "negative_prompt": "blurry, low quality, watermark, deformed, ugly, distorted face",
                "width": 1024,
                "height": 1024,
                "num_outputs": 1,
            },
        }
        r = await client.post(
            "https://api.replicate.com/v1/predictions", json=payload, headers=headers
        )
        r.raise_for_status()
        pred_id = r.json()["id"]

        for _ in range(60):
            await asyncio.sleep(3)
            r = await client.get(
                f"https://api.replicate.com/v1/predictions/{pred_id}", headers=headers
            )
            r.raise_for_status()
            pred = r.json()
            if pred["status"] == "succeeded":
                output_url = pred["output"][0]
                resp = await client.get(output_url)
                resp.raise_for_status()
                return resp.content
            elif pred["status"] == "failed":
                raise RuntimeError(f"Replicate prediction failed: {pred.get('error')}")

        raise RuntimeError("Replicate prediction timed out")


async def generate_avatar_bytes(input_image_path: str, theme: str, outfit: str, extras: dict = None) -> bytes:
    from app.utils import read_bytes

    ref_bytes = read_bytes(input_image_path)

    ext = input_image_path.rsplit(".", 1)[-1].lower()
    media_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    media_type = media_type_map.get(ext, "image/jpeg")

    # Step 1: Claude Vision analyzes the portrait and crafts a rich generation prompt
    prompt = _analyze_portrait_with_claude(ref_bytes, media_type, theme, outfit)

    # Step 2: Generate image with configured provider
    provider = os.getenv("IMAGE_PROVIDER", "STABILITY").upper()

    if provider == "STABILITY":
        return await _generate_with_stability(prompt)
    elif provider == "REPLICATE":
        return await _generate_with_replicate(prompt)
    else:
        raise RuntimeError(f"Unsupported IMAGE_PROVIDER: {provider}")
