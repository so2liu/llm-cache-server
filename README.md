# LLM Cache Proxy

LLM Cache Proxy is a FastAPI-based application that serves as a caching layer for OpenAI's API. It intercepts requests to the OpenAI API, caches responses, and serves cached responses for identical requests, potentially reducing API costs and improving response times.

## TL;DR: Quick Start with Docker

```bash
# Run the container
docker run -p 9999:9999 \
  -v $(pwd)/data:/app/data \
  ghcr.io/so2liu/llm-cache-server:latest
```

OR

```bash
# Run the container with custom API key
docker run -p 9999:9999 \
  -e OPENAI_API_KEY=your_api_key_here \
  -e OPENAI_BASE_URL=https://api.openai.com/v1 \
  -v $(pwd)/data:/app/data \
  ghcr.io/so2liu/llm-cache-server:latest
```

The proxy is now available at http://localhost:9999

Use /cache/chat/completions for cached requests

Use /chat/completions for uncached requests

## Features

-   Caches responses from OpenAI's API
-   Supports both streaming and non-streaming responses
-   Compatible with OpenAI's chat completion endpoint
-   Configurable via environment variables
-   Dockerized for easy deployment
-   Persistent cache storage

## Prerequisites

-   Python 3.12+
-   Docker (optional, for containerized deployment)

## Installation

1. Clone the repository:

    ```
    git clone https://github.com/so2liu/llm-cache-server.git
    cd llm-cache-server
    ```

2. Install the required packages:
    ```
    pip install -r requirements.txt
    ```

## Configuration

Set the following environment variables:

-   `OPENAI_API_KEY`: Your OpenAI API key
-   `OPENAI_BASE_URL`: The base URL for OpenAI's API (default: https://api.openai.com/v1)

You can set these in a `.env` file in the project root.

## Usage

### Running Locally

1. Start the server:

    ```
    python -m app.main
    ```

2. The server will be available at `http://localhost:9999`

### Using Docker

**Recommended: Use pre-built image from GitHub Container Registry**

```bash
docker run -p 9999:9999 \
  -e OPENAI_API_KEY=your_api_key_here \
  -e OPENAI_BASE_URL=https://api.openai.com/v1 \
  -v $(pwd)/data:/app/data \
  ghcr.io/so2liu/llm-cache-server:latest
```

**Or build locally:**

1. Build the Docker image:

    ```
    docker build -t llm-cache-server .
    ```

2. Run the container with persistent storage:

    ```
    docker run -p 9999:9999 \
      -e OPENAI_API_KEY=your_api_key_here \
      -e OPENAI_BASE_URL=https://api.openai.com/v1 \
      -v $(pwd)/data:/app/data \
      llm-cache-server
    ```

    This command mounts a `data` directory from your current working directory to the `/app/data` directory in the container, ensuring that the cache persists between container restarts.

## API Endpoints

-   `/chat/completions`: Proxies requests to OpenAI's chat completion API without caching
-   `/cache/chat/completions`: Proxies requests to OpenAI's chat completion API with caching

Both endpoints accept the same parameters as OpenAI's chat completion API.

## Development

To run the application in verbose mode, use the `--verbose` flag:

```
python -m app.main --verbose
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
