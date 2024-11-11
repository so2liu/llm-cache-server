import os
import openai
import json
import hashlib
from typing import Iterator
import asyncio
from .models import ChatCompletionRequest
from .cache import cache_response
from openai.types.chat import ChatCompletionChunk


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


def merge_chunks(chunks: list[ChatCompletionChunk]):
    first_chunk = chunks[0].to_dict()
    first_chunk["choices"][0]["delta_list"] = [first_chunk["choices"][0]["delta"]]
    merged_chunks = [first_chunk]
    for chunk in chunks[1:]:
        if not chunk.usage and not chunk.choices[0].finish_reason:
            merged_chunks[-1]["choices"][0]["delta_list"].append(
                chunk.choices[0].delta.to_dict()
            )
        else:
            merged_chunks.append(chunk.to_dict())
    return merged_chunks


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
            response_chunks.append(chunk)
        yield f"data: {json.dumps(chunk_dict)}\n\n"
        await asyncio.sleep(0.01)
    yield "data: [DONE]\n\n"

    if use_cache and request_hash is not None:
        cache_response(
            request_hash=request_hash,
            prompt=chat_request.model_dump_json(),
            response=json.dumps(merge_chunks(response_chunks)),
            is_stream=True,
        )
