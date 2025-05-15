from typing import Literal
import openai
import json
import hashlib
import asyncio
from .models import ChatCompletionRequest
from .cache import cache_response
from openai.types.chat import ChatCompletionChunk
from .env_config import env_config
import json

ProviderType = Literal["openrouter", "aliyun", "deepseek"] | None


def get_openai_client(authorization: str, provider: ProviderType):
    provider_base_url = {
        "openrouter": "https://openrouter.ai/api/v1",
        "aliyun": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }

    api_key = (
        authorization.split(" ")[1] if authorization else env_config.OPENAI_API_KEY
    )

    base_url = provider_base_url[provider] if provider else env_config.OPENAI_BASE_URL

    return openai.AsyncOpenAI(base_url=base_url, api_key=api_key)


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
    client: openai.AsyncOpenAI,
    chat_request: ChatCompletionRequest,
    use_cache: bool,
    request_hash: str,
):
    first_chunk = True
    response_chunks = []
    response = await client.chat.completions.create(
        **chat_request.model_dump(exclude={"stream"}),
        stream=True,
    )

    async for chunk in response:
        if first_chunk:
            first_chunk = False

        # use dict to avoid json serialization \n
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
