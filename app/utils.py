import asyncio
import functools
import hashlib
import json
import time
from typing import Any, Literal

import openai
from openai.types.chat import ChatCompletionChunk
from pydantic import BaseModel
from rich import print

from .cache import cache_response
from .env_config import env_config
from .models import ChatCompletionRequest

ProviderType = Literal["openrouter", "aliyun", "deepseek", "bigmodel"] | str | None


# Pydantic models for GLM-4.6 streaming chunks
class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    index: int
    type: str
    function: ToolCallFunction


class ChunkDelta(BaseModel):
    role: str | None = None
    reasoning_content: str | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None

    def has_reasoning(self) -> bool:
        """Check if this delta contains reasoning_content"""
        return self.reasoning_content is not None and len(self.reasoning_content) > 0

    def transform_reasoning_to_content(self, add_opening_tag: bool = False, add_closing_tag: bool = False) -> None:
        """
        Transform reasoning_content to content with optional <think> tags.

        Args:
            add_opening_tag: Whether to add <think> at the beginning
            add_closing_tag: Whether to add </think> at the end
        """
        if not self.reasoning_content:
            return

        reasoning = self.reasoning_content
        if add_opening_tag:
            reasoning = f"<think>{reasoning}"
        if add_closing_tag:
            reasoning = f"{reasoning}</think>"

        # Prepend reasoning to content
        self.content = f"{reasoning}{self.content or ''}"
        self.reasoning_content = None


class ChunkChoice(BaseModel):
    index: int
    delta: ChunkDelta
    finish_reason: str | None = None


class StreamChunk(BaseModel):
    id: str
    created: int
    model: str
    choices: list[ChunkChoice]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamChunk":
        """Create StreamChunk from dict (handles OpenAI's to_dict() output)"""
        return cls.model_validate(data)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, excluding None values"""
        return self.model_dump(exclude_none=True, by_alias=True)

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
def merge_chunks(chunks: list[ChatCompletionChunk]) -> list[dict[str, Any]]:
    first_chunk: dict[str, Any] = chunks[0].to_dict()
    first_chunk["choices"][0]["delta_list"] = [first_chunk["choices"][0]["delta"]]
    merged_chunks: list[dict[str, Any]] = [first_chunk]
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

    # State tracking for GLM-4.6 reasoning_content transformation
    is_glm46 = chat_request.model == "glm-4.6"
    reasoning_started = False
    prev_chunk: StreamChunk | None = None

    async for raw_chunk in response:
        if first_chunk:
            first_chunk = False

        # Parse chunk using Pydantic model
        chunk = StreamChunk.from_dict(raw_chunk.to_dict())

        # Transform GLM-4.6 streaming chunks with state tracking
        if is_glm46:
            # Check if current chunk has reasoning_content
            current_has_reasoning = any(choice.delta.has_reasoning() for choice in chunk.choices)

            # Process previous chunk if exists
            if prev_chunk is not None:
                prev_has_reasoning = any(choice.delta.has_reasoning() for choice in prev_chunk.choices)

                # Transform previous chunk
                if prev_has_reasoning:
                    for choice in prev_chunk.choices:
                        if choice.delta.has_reasoning():
                            # Determine if we need to add opening/closing tags
                            add_opening = not reasoning_started
                            add_closing = not current_has_reasoning

                            if add_opening:
                                reasoning_started = True
                            if add_closing:
                                reasoning_started = False

                            choice.delta.transform_reasoning_to_content(
                                add_opening_tag=add_opening, add_closing_tag=add_closing
                            )

                # Yield previous chunk
                yield f"data: {json.dumps(prev_chunk.to_dict())}\n\n"
                if simulate and use_cache:
                    await asyncio.sleep(0.05)

            # Store current chunk as previous for next iteration
            prev_chunk = chunk
        else:
            # Non-GLM-4.6 model, process normally
            yield f"data: {json.dumps(chunk.to_dict())}\n\n"
            if simulate and use_cache:
                await asyncio.sleep(0.05)

        if use_cache:
            response_chunks.append(raw_chunk)

    # Process and yield the last chunk for GLM-4.6
    if is_glm46 and prev_chunk is not None:
        last_has_reasoning = any(choice.delta.has_reasoning() for choice in prev_chunk.choices)

        if last_has_reasoning:
            for choice in prev_chunk.choices:
                if choice.delta.has_reasoning():
                    # For the last chunk with reasoning, add opening tag if not started yet
                    # and always add closing tag
                    choice.delta.transform_reasoning_to_content(
                        add_opening_tag=not reasoning_started, add_closing_tag=True
                    )

        yield f"data: {json.dumps(prev_chunk.to_dict())}\n\n"
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


def transform_glm46_non_streaming_response(response_dict: dict) -> dict:
    """
    Transform GLM-4.6 non-streaming response to fix quirks.

    Fixes:
    1. tool_calls structure: Convert list of lists to flat list
    2. reasoning_content: Convert to <think>...</think> format and prepend to content
    """
    for choice in response_dict.get("choices", []):
        message = choice.get("message", {})

        # Fix 1: Convert tool_calls list of lists to flat list
        # tool_calls = message.get("tool_calls")
        # if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
        #     if isinstance(tool_calls[0], list):
        #         message["tool_calls"] = tool_calls[0]

        # Fix 2: Convert reasoning_content to <think>...</think>
        if "reasoning_content" in message:
            reasoning = message.pop("reasoning_content")
            if reasoning:
                current_content = message.get("content", "")
                message["content"] = f"<think>{reasoning}</think>{current_content}"

    return response_dict
