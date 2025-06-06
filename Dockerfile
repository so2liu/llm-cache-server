# Use the official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

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

# Run the application
ENTRYPOINT ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "9999"]
