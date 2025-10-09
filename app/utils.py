import asyncio
import functools
import hashlib
import json
import time
from typing import Literal

import openai
from openai.types.chat import ChatCompletionChunk
from rich import print

from .cache import cache_response
from .env_config import env_config
from .models import ChatCompletionRequest

ProviderType = Literal["openrouter", "aliyun", "deepseek", "bigmodel"] | None

PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "aliyun": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "bigmodel": "https://open.bigmodel.cn/api/paas/v4",
}

PROVIDER_TEST_ORDER: list[ProviderType] = ["openrouter", "aliyun", "deepseek", "bigmodel"]

# Test models for each provider (lightweight models to minimize cost/latency)
PROVIDER_TEST_MODELS = {
    "openrouter": "gpt-3.5-turbo",
    "aliyun": "qwen-turbo",
    "deepseek": "deepseek-chat",
    "bigmodel": "glm-4-flash",
}


def timeit(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        print(f"Function {func.__name__} took {execution_time:.4f} seconds")
        return result

    return wrapper


def get_openai_client(authorization: str, provider: ProviderType):
    api_key = authorization.split(" ")[1] if authorization else env_config.OPENAI_API_KEY

    base_url = PROVIDER_BASE_URLS[provider] if provider else env_config.OPENAI_BASE_URL

    return openai.AsyncOpenAI(base_url=base_url, api_key=api_key)


async def detect_provider(api_key: str) -> ProviderType:
    """
    Detect which provider an API key belongs to by testing /models endpoint concurrently.

    Args:
        api_key: The API key to test

    Returns:
        The detected provider name, or None (OpenAI) if all tests fail
    """
    from .provider_registry import cache_provider, get_cached_provider

    # Check cache first
    cached = get_cached_provider(api_key)
    if cached is not None:
        print(f"Using cached provider: {cached if cached else 'OpenAI'}")
        return cached

    async def test_provider(provider: ProviderType) -> tuple[ProviderType, bool]:
        """Test a single provider's API key with a minimal completion request."""
        if provider is None:
            raise ValueError("Provider cannot be None in test_provider")
        try:
            base_url = PROVIDER_BASE_URLS[provider]
            test_model = PROVIDER_TEST_MODELS[provider]
            client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=5.0)

            # Make a minimal test request with provider-specific model to properly validate auth
            await client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return provider, True
        except Exception:
            return provider, False

    # Test all providers concurrently
    tasks = [test_provider(provider) for provider in PROVIDER_TEST_ORDER]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Find first successful provider (maintaining priority order)
    for provider in PROVIDER_TEST_ORDER:
        for result_provider, success in results:
            if result_provider == provider and success:
                print(f"Detected provider: {provider}")
                cache_provider(api_key, provider)
                return provider

    # Default to None (OpenAI) if all providers fail
    print("No provider detected, defaulting to OpenAI")
    cache_provider(api_key, None)
    return None


@timeit
def get_request_hash(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


@timeit
def merge_chunks(chunks: list[ChatCompletionChunk]):
    first_chunk = chunks[0].to_dict()
    first_chunk["choices"][0]["delta_list"] = [first_chunk["choices"][0]["delta"]]
    merged_chunks = [first_chunk]
    for chunk in chunks[1:]:
        if not chunk.usage and not chunk.choices[0].finish_reason:
            merged_chunks[-1]["choices"][0]["delta_list"].append(chunk.choices[0].delta.to_dict())
        else:
            merged_chunks.append(chunk.to_dict())
    return merged_chunks


async def stream_response(
    client: openai.AsyncOpenAI,
    chat_request: ChatCompletionRequest,
    use_cache: bool,
    request_hash: str,
    simulate: bool = False,
):
    first_chunk = True
    response_chunks = []
    body = chat_request.model_dump(exclude={"stream"}, exclude_none=True)
    try:
        response = await client.chat.completions.create(**body, stream=True)
    except Exception as e:
        print(body)
        raise e

    async for chunk in response:
        if first_chunk:
            first_chunk = False

        # use dict to avoid json serialization \n
        chunk_dict = chunk.to_dict()
        if use_cache:
            response_chunks.append(chunk)
        yield f"data: {json.dumps(chunk_dict)}\n\n"
        if simulate and use_cache:
            await asyncio.sleep(0.05)
    yield "data: [DONE]\n\n"

    if use_cache and request_hash is not None:
        cache_response(
            request_hash=request_hash,
            prompt=chat_request.model_dump_json(),
            response=json.dumps(merge_chunks(response_chunks)),
            is_stream=True,
        )
