import os
from typing import Any, Dict
import httpx
from agno.agent import Agent
from agno.models.openai import OpenAIChat 
from agno.tools import Tool 
from agno import AgentResult

'''
Giải thích ngắn: ImageGenTool là tool Agno thực hiện HTTP request đến provider (Replicate / Stability / OpenAI). 
generate_avatar_bytes chạy agent, agent sẽ gọi tool và trả bytes. 
Bạn phải kiểm tra và điều chỉnh chi tiết provider (cách gọi Replicate/ Stability/ OpenAI thực tế) theo docs provider.
'''

class ImageGenTool(Tool):
    def __init__(self, provider: str):
        super().__init__(name="image_gen", description="Generate image from prompt and reference image")
        self.provider = provider.upper()

    async def _call_provider(self, prompt: str, ref_image_bytes: bytes, params: Dict[str, Any]) -> bytes:
        # choose provider implementation
        if self.provider == "REPLICATE":
            # example: call Replicate REST API (pseudo)
            # Replicate expects base64 or multipart per model spec; here is a basic example using httpx
            token = os.getenv("REPLICATE_API_TOKEN")
            model = params.get("replicate_model", "stability-ai/stable-diffusion")
            # This is a simplified call; adapt per chosen model on Replicate
            headers = {"Authorization": f"Token {token}"}
            async with httpx.AsyncClient(timeout=120) as client:
                # Using replicate REST: POST /v1/predictions; payload differs per model
                payload = {
                    "version": model,
                    "input": {"prompt": prompt}
                }
                r = await client.post("https://api.replicate.com/v1/predictions", json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                # replicate returns a prediction; you may need to poll to get output
                # For MVP, assume direct output url present (in reality you often poll)
                output_url = data.get("output")[0]
                # fetch binary
                resp = await client.get(output_url)
                resp.raise_for_status()
                return resp.content

        elif self.provider == "STABILITY":
            token = os.getenv("STABILITY_API_KEY")
            async with httpx.AsyncClient(timeout=120) as client:
                headers = {"Authorization": f"Bearer {token}"}
                payload = {"text_prompts": [{"text": prompt}], "cfg_scale": params.get("cfg_scale", 7.0)}
                r = await client.post("https://api.stability.ai/v1/generation/stable-diffusion-v1-5/text-to-image", json=payload, headers=headers)
                r.raise_for_status()
                # stability may return base64 images
                j = r.json()
                b64 = j["artifacts"][0]["base64"]
                import base64
                return base64.b64decode(b64)

        elif self.provider == "OPENAI":
            # Example for OpenAI Images API (DALL·E style). Adjust to real endpoint & SDK you use.
            token = os.getenv("OPENAI_API_KEY")
            async with httpx.AsyncClient(timeout=120) as client:
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                payload = {"prompt": prompt, "size": "1024x1024"}
                r = await client.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers)
                r.raise_for_status()
                j = r.json()
                b64 = j["data"][0]["b64_json"]
                import base64
                return base64.b64decode(b64)
        else:
            raise RuntimeError("Unsupported provider")

    async def __call__(self, prompt: str, ref_image_bytes: bytes = None, params: Dict[str, Any] = None) -> bytes:
        params = params or {}
        return await self._call_provider(prompt, ref_image_bytes, params)


# compose agent
def build_avatar_agent(provider: str = None) -> Agent:
    provider = provider or os.getenv("IMAGE_PROVIDER", "REPLICATE")
    image_tool = ImageGenTool(provider)

    # Use text model for reasoning (optional). This model helps build a better prompt.
    text_model = OpenAIChat(id=os.getenv("OPENAI_MODEL_ID", "gpt-4o")) if os.getenv("OPENAI_API_KEY") else None

    agent = Agent(
        name="AvatarGenerator",
        role="Produce a high-quality avatar image based on user-provided portrait and style instructions.",
        model=text_model,
        tools=[image_tool],
        instructions=(
            "You are an avatar generation assistant. Use the provided image as a reference. "
            "When calling the image_gen tool, pass a rich prompt describing lighting, pose, clothing, and style."
        ),
        show_tool_calls=True,
        markdown=False
    )
    return agent

# function worker will call:
async def generate_avatar_bytes(input_image_path: str, theme: str, outfit: str, extras: dict = None) -> bytes:
    from app.utils import read_bytes
    ref_bytes = read_bytes(input_image_path)
    agent = build_avatar_agent()
    # Build a rich prompt
    prompt = (
        f"Create a photorealistic portrait using the reference image. Style: {theme}. Clothing: {outfit}. "
        "High resolution, natural lighting, face clearly visible, no watermark. Keep subject identity same as reference."
    )
    # Agent should decide to call image_gen tool with prompt & ref image
    # Depending on Agno version you may call agent.run or agent.step/run_async — we call run() and expect AgentResult
    result: AgentResult = await agent.run(prompt, tools_kwargs={"image_gen": {"ref_image_bytes": ref_bytes, "params": extras or {}}})
    # parse result: try to get media bytes from tool call result
    # Agno's actual AgentResult API may vary — we attempt to get tool outputs
    if result and hasattr(result, "tool_results") and result.tool_results:
        # first tool result likely contains bytes or url
        first = result.tool_results[0]
        # if tool returned bytes directly
        if isinstance(first, (bytes, bytearray)):
            return bytes(first)
        # if tool returned dict with 'bytes' or 'content'
        if isinstance(first, dict):
            if "bytes" in first:
                return first["bytes"]
            if "content" in first:
                return first["content"]
            if "url" in first:
                # fetch
                async with httpx.AsyncClient() as client:
                    resp = await client.get(first["url"])
                    resp.raise_for_status()
                    return resp.content
    # Fallback: if agent returned text with a url included
    text = getattr(result, "text", None)
    if text:
        # try to find first URL in text and fetch it
        import re, httpx
        m = re.search(r"https?://\S+", text)
        if m:
            url = m.group(0)
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content

    raise RuntimeError("Agent did not return image bytes")
