# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM Cache Proxy is a FastAPI-based caching layer for OpenAI and other LLM provider APIs. It intercepts requests, caches responses, and serves cached responses for identical requests to reduce API costs and improve response times.

## Development Commands

### Running the application
```bash
# Using uv (preferred)
uv run python -m app.main

# Or using Docker
docker compose up

# With verbose mode
uv run python -m app.main --verbose
```

### Running tests
```bash
# Run the test suite
uv run python test_api.py

# Note: Ensure the server is running on localhost:9999 before running tests
```

### Package management
```bash
# Install/sync dependencies
uv sync

# Add a new dependency
uv add <package-name>

# Update dependencies
uv lock --upgrade-package <package-name>
```

### Docker operations
```bash
# Build the image
docker build -t llm-cache-proxy .

# Run with persistent storage
docker run -p 9999:9999 -v $(pwd)/data:/app/data so2liu/llm-cache-proxy
```

## Architecture Overview

### Core Components

1. **FastAPI Application (`app/main.py`)**
   - Entry point for all HTTP requests
   - Provides both cached (`/cache/chat/completions`) and non-cached (`/chat/completions`) endpoints
   - Supports multiple LLM providers (OpenAI, OpenRouter, Aliyun, DeepSeek, BigModel)
   - Handles both streaming and non-streaming responses

2. **Cache Layer (`app/cache.py`)**
   - SQLite-based cache implementation
   - Stores request hashes with their corresponding responses
   - Handles both streaming and non-streaming response caching

3. **Database (`app/database.py`)**
   - SQLite database for persistent cache storage
   - Automatically creates database if it doesn't exist
   - Located at `data/llm_cache.db`

4. **Environment Configuration (`app/env_config.py`)**
   - Manages environment variables
   - Supports `.env` file for local development
   - Key variables: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LOG_MESSAGE`

5. **Telemetry (`app/telemetry/sentry_settings.py`)**
   - Sentry integration for error tracking
   - Configurable via `SENTRY_DSN` environment variable

### Request Flow

1. Client sends request to `/cache/chat/completions` or `/chat/completions`
2. Request is validated and converted to `ChatCompletionRequest` model
3. For cached endpoints:
   - Request hash is generated from the request body
   - Cache is checked for existing response
   - If found, cached response is returned
   - If not found, request is forwarded to LLM provider
4. Response is returned to client (and cached if using cache endpoint)

### Provider Support

The proxy supports multiple LLM providers through URL routing:
- OpenAI (default)
- OpenRouter (`/{provider}/chat/completions` where provider="openrouter")
- Aliyun/Qwen
- DeepSeek
- BigModel/GLM

Each provider has its own base URL configured in `app/utils.py`.

### Key Technical Details

- Uses `uv` for Python package management (Python 3.11+)
- Async/await pattern throughout for better concurrency
- Streaming responses handled with Server-Sent Events (SSE)
- Request hashing uses SHA256 for cache key generation
- Database operations are synchronous (potential optimization point)
- CORS enabled for all origins