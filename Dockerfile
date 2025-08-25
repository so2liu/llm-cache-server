# Use the official Python runtime as a parent image
FROM python:3.12-slim

# Install uv
RUN apt-get update && apt-get install -y curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Set the working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# This layer will be cached unless pyproject.toml or uv.lock changes
RUN uv sync --frozen --no-install-project

# Copy the rest of the application
COPY . /app

# Install the project itself
RUN uv sync --frozen

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser

# Change the ownership of the database directory to appuser
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Switch to non-root user
# USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OPENAI_API_KEY=""
ENV OPENAI_BASE_URL="https://api.openai.com/v1"

# Make port 9999 available to the world outside this container
EXPOSE 9999

WORKDIR /app/app

# Run the application using uv
ENTRYPOINT ["uv", "run", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "9999"]