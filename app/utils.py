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

ProviderType = Literal["openrouter", "aliyun", "deepseek", "bigmodel"] | str | None

# Built-in provider base URLs
BUILTIN_BASE_URLS = [
    "https://openrouter.ai/api/v1",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "https://api.deepseek.com/v1",
    "https://open.bigmodel.cn/api/paas/v4",
]


def get_all_base_urls() -> list[str]:
    """Get all base URLs (additional from env + built-in)"""
    from .env_config import env_config

    additional = env_config.get_additional_base_urls()

    if additional:
        print(f"Loaded {len(additional)} additional base URL(s): {additional}")

    # Additional URLs first, then built-in ones
    return additional + BUILTIN_BASE_URLS


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

    # provider is now the base URL string directly
    base_url = provider if provider else env_config.OPENAI_BASE_URL

    return openai.AsyncOpenAI(base_url=base_url, api_key=api_key)


async def detect_provider(api_key: str, model: str) -> ProviderType:
    """
    Detect which base URL an API key belongs to by testing with the user's requested model.

    Args:
        api_key: The API key to test
        model: The model name from the user's request

    Returns:
        The detected base URL string, or None if all tests fail

    Raises:
        ValueError: If all base URLs fail with details about accepted base URLs
    """
    from .provider_registry import cache_provider, get_cached_provider

    # Check cache first
    cached = get_cached_provider(api_key)
    if cached is not None:
        print(f"Using cached base URL: {cached if cached else 'OpenAI'}")
        return cached

    all_base_urls = get_all_base_urls()

    async def test_base_url(base_url: str) -> tuple[str, bool, str]:
        """Test a single base URL with the user's requested model."""
        try:
            client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=5.0)

            # Test with the user's requested model and a simple test message
            await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return base_url, True, ""
        except Exception as e:
            return base_url, False, str(e)

    # Test all base URLs concurrently
    tasks = [test_base_url(base_url) for base_url in all_base_urls]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Find first successful base URL (maintaining priority order)
    for base_url in all_base_urls:
        for result_base_url, success, _ in results:
            if result_base_url == base_url and success:
                print(f"Detected base URL: {base_url}")
                cache_provider(api_key, base_url)
                return base_url

    # If all base URLs failed, raise an error with accepted base URLs
    accepted_urls = "\n".join([f"  - {url}" for url in all_base_urls])
    error_msg = f"All base URLs failed. Accepted base URLs:\n{accepted_urls}"
    print(f"No base URL detected: {error_msg}")
    raise ValueError(error_msg)


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
