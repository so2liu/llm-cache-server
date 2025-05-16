import json
from .database import get_db_connection
from .models import ChatCompletionResponse
from fastapi.responses import StreamingResponse
import copy
import functools
import time


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


@timeit
def check_cache(request_hash: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value, is_stream FROM cache WHERE hashed_key = ?", (request_hash,)
    )
    result = cursor.fetchone()
    conn.close()
    if result:
        cached_response, is_stream = result
        is_stream = bool(is_stream)
        if is_stream:
            return StreamingResponse(
                stream_cache_response(json.loads(cached_response)),
                media_type="text/event-stream",
            )
        else:
            return ChatCompletionResponse(**json.loads(cached_response))
    return None


@timeit
def cache_response(request_hash: str, prompt: str, response: str, is_stream: bool):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO cache 
        (hashed_key, key, value, is_stream, timestamp) 
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (request_hash, prompt, response, is_stream),
    )
    conn.commit()
    conn.close()


async def stream_cache_response(cached_chunks: list):
    first_chunk = cached_chunks[0]
    for chunk in cached_chunks:
        try:
            for delta in chunk["choices"][0]["delta_list"]:
                new_chunk = copy.deepcopy(first_chunk)
                del new_chunk["choices"][0]["delta_list"]
                new_chunk["choices"][0]["delta"] = delta
                yield f"data: {json.dumps(new_chunk)}\n\n"
        except KeyError:
            yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"
