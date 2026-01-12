# Use the official Python runtime as a parent image
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set the working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (frozen lockfile for reproducibility)
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application
COPY . /app

# Install the project itself
RUN uv sync --frozen --no-dev

# Final stage - minimal runtime image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy only the virtual environment and app from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    OPENAI_API_KEY="" \
    OPENAI_BASE_URL="https://api.openai.com/v1" \
    PATH="/app/.venv/bin:$PATH"

# Make port 9999 available to the world outside this container
EXPOSE 9999

WORKDIR /app/app

# Run the application directly
ENTRYPOINT ["python", "-m", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "9999"]