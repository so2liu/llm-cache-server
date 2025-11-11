import copy
import json
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from rich import print

from .cache import cache_response, check_cache
from .database import init_db
from .env_config import env_config
from .models import ChatCompletionRequest, ChatCompletionResponse
from .telemetry.sentry_settings import init_sentry
from .utils import ProviderType, detect_provider, get_openai_client, get_request_hash, stream_response

# Initialize Sentry
init_sentry()

# Initialize the database when the application starts
init_db()

app = FastAPI()

# Add CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def process_chat_request(
    request: Request,
    use_cache: bool,
    authorization: Annotated[str, Header()],
    provider: ProviderType = None,
    simulate: bool = False,
):
    body = await request.json()

    # Special handling for GLM-4.6 model
    if body.get("model") == "glm-4.6":
        if "max_tokens" not in body or body["max_tokens"] is None:
            body["max_tokens"] = 1
            if env_config.LOG_MESSAGE:
                print("GLM-4.6 model: Auto-filled max_tokens with 1")
        if "stream" not in body or body["stream"] is None:
            body["stream"] = True
            if env_config.LOG_MESSAGE:
                print("GLM-4.6 model: Auto-filled stream with True")

    if env_config.LOG_MESSAGE:
        print(json.dumps(body, indent=2, ensure_ascii=False))
        print("Verbose: Message contents")
        for message in body.get("messages", []):
            print(f"Role: {message.get('role')}")
            print(f"Content: {message.get('content')}")
            print("---")

        print("\nVerbose: Request body (excluding message contents)")
        body_without_content = copy.deepcopy(body)
        if "messages" in body_without_content:
            for message in body_without_content["messages"]:
                if "content" in message:
                    message["content"] = "[CONTENT REMOVED]"
        print(json.dumps(body_without_content, indent=2, ensure_ascii=False))

    chat_request = ChatCompletionRequest(**body)

    # Auto-detect provider if not specified
    if provider is None:
        api_key = authorization.split(" ")[1] if authorization else env_config.OPENAI_API_KEY
        provider = await detect_provider(api_key, chat_request.model)

    client = get_openai_client(authorization, provider)

    if use_cache:
        request_hash = get_request_hash(body)
        cached_response = check_cache(request_hash, simulate)

        if cached_response:
            print("hit cache")
            return cached_response

    if chat_request.stream:
        stream_gen = stream_response(
            client,
            chat_request,
            use_cache,
            request_hash if use_cache else "",
            simulate,
        )
        return StreamingResponse(
            stream_gen,
            media_type="text/event-stream",
        )
    else:
        response = await client.chat.completions.create(**chat_request.model_dump(exclude_none=True))

        if use_cache:
            print("add to cache")
            cache_response(request_hash, json.dumps(body), response.to_json(), False)

        try:
            return ChatCompletionResponse(**response.to_dict())
        except Exception:
            return {"error": response.to_dict()}


@app.post("/cache/chat/completions")
@app.post("/{provider}/cache/chat/completions")
@app.post("/cache/v1/chat/completions")
@app.post("/{provider}/cache/v1/chat/completions")
@app.post("/simulate/cache/chat/completions")
@app.post("/simulate/{provider}/cache/chat/completions")
@app.post("/simulate/cache/v1/chat/completions")
@app.post("/simulate/{provider}/cache/v1/chat/completions")
async def cache_chat_completion(
    request: Request,
    authorization: Annotated[str, Header()],
    provider: ProviderType = None,
):
    simulate = request.url.path.startswith("/simulate/")
    try:
        return await process_chat_request(
            request, use_cache=True, authorization=authorization, provider=provider, simulate=simulate
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/chat/completions")
@app.post("/{provider}/chat/completions")
@app.post("/v1/chat/completions")
@app.post("/{provider}/v1/chat/completions")
@app.post("/simulate/chat/completions")
@app.post("/simulate/{provider}/chat/completions")
@app.post("/simulate/v1/chat/completions")
@app.post("/simulate/{provider}/v1/chat/completions")
async def chat_completion(
    request: Request,
    authorization: Annotated[str, Header()],
    provider: ProviderType = None,
):
    simulate = request.url.path.startswith("/simulate/")
    try:
        return await process_chat_request(
            request, use_cache=False, authorization=authorization, provider=provider, simulate=simulate
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/cache/models")
@app.get("/models")
@app.get("/{provider}/cache/models")
async def get_models(authorization: Annotated[str, Header()], provider: ProviderType):
    try:
        client = get_openai_client(authorization, provider)
        return await client.models.list()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9999)
