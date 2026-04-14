FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure standard permissions
RUN chmod +x *.py

# Expose port
EXPOSE 8080

# Start server using the FastMCP sse loop natively
CMD ["python", "server.py"]
