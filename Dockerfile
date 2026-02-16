FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application
COPY config/ config/
COPY src/ src/
COPY schemas/ schemas/

# Create log directory
RUN mkdir -p /app/logs

# Run pipeline
CMD ["python3", "-m", "src.pipeline"]
