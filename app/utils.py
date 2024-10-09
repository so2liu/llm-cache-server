import os
import openai
import json
import hashlib
from typing import Iterator
import asyncio
from .models import ChatCompletionRequest
from .cache import cache_response


def get_openai_client(auth_header: str):
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ")[1]
        api_key = token if len(token) > 10 else os.environ.get("OPENAI_API_KEY")
    else:
        api_key = os.environ.get("OPENAI_API_KEY")

    return openai.OpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL", None),
        api_key=api_key,
    )


def get_request_hash(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


async def stream_response(
    client: openai.OpenAI,
    chat_request: ChatCompletionRequest,
    use_cache: bool,
    request_hash: str | None = None,
):
    response_chunks = []
    response = client.chat.completions.create(
        **chat_request.model_dump(exclude={"stream"}),
        stream=True,
    )

    for chunk in response:
        chunk_dict = chunk.to_dict()
        if use_cache:
            response_chunks.append(chunk_dict)
        yield f"data: {json.dumps(chunk_dict)}\n\n"
        await asyncio.sleep(0.01)
    yield "data: [DONE]\n\n"

    if use_cache and request_hash is not None:
        cache_response(
            request_hash=request_hash,
            prompt=chat_request.model_dump_json(),
            response=json.dumps(response_chunks),
            is_stream=True,
        )
