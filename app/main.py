from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
import copy
from .models import ChatCompletionRequest, ChatCompletionResponse
from .database import init_db
from .cache import check_cache, cache_response
from .utils import get_openai_client, get_request_hash, stream_response
from fastapi.middleware.cors import CORSMiddleware
from .env_config import env_config

# Initialize the database when the application starts
init_db()

app = FastAPI()

# Add CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # Allow all sources, you can set specific domains based on your needs
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all request headers
)


async def process_chat_request(request: Request, use_cache: bool):
    body = await request.json()

    print(json.dumps(body, indent=2, ensure_ascii=False))

    if env_config.VERBOSE:
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
    client = get_openai_client(request.headers.get("Authorization"))

    if use_cache:
        request_hash = get_request_hash(body)
        cached_response = check_cache(request_hash)
        if cached_response:
            print("hit cache")
            return cached_response

    if chat_request.stream:
        return StreamingResponse(
            stream_response(
                client, chat_request, use_cache, request_hash if use_cache else ""
            ),
            media_type="text/event-stream",
        )
    else:
        response = client.chat.completions.create(**chat_request.model_dump())
        if use_cache:
            print("add to cache")
            cache_response(request_hash, json.dumps(body), response.to_json(), False)
        try:
            return ChatCompletionResponse(**response.to_dict())
        except Exception as e:
            return {"error": response.to_dict()}


@app.post("/cache/chat/completions")
@app.post("/cache/v1/chat/completions")
async def cache_chat_completion(request: Request):
    try:
        return await process_chat_request(request, use_cache=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/chat/completions")
@app.post("/v1/chat/completions")
async def chat_completion(request: Request):
    try:
        return await process_chat_request(request, use_cache=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/cache/models")
@app.get("/models")
async def get_models(request: Request):
    try:
        client = get_openai_client(request.headers.get("Authorization"))
        return client.models.list()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9999)
