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
from typing import Annotated
from fastapi import Header

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
    request: Request, use_cache: bool, authorization: Annotated[str, Header()]
):
    body = await request.json()

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
    client = get_openai_client(authorization)

    if use_cache:
        request_hash = get_request_hash(body)
        cached_response = check_cache(request_hash)

        if cached_response:
            print("hit cache")
            return cached_response

    if chat_request.stream:
        stream_gen = stream_response(
            client,
            chat_request,
            use_cache,
            request_hash if use_cache else "",
        )
        return StreamingResponse(
            stream_gen,
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
async def cache_chat_completion(
    request: Request, authorization: Annotated[str, Header()]
):
    try:
        return await process_chat_request(
            request, use_cache=True, authorization=authorization
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/chat/completions")
@app.post("/v1/chat/completions")
async def chat_completion(request: Request, authorization: Annotated[str, Header()]):
    try:
        return await process_chat_request(
            request, use_cache=False, authorization=authorization
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/cache/models")
@app.get("/models")
async def get_models(request: Request, authorization: Annotated[str, Header()]):
    try:
        client = get_openai_client(authorization)
        return client.models.list()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9999)
