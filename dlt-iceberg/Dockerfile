FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install all dependencies including dlt from PyPI
RUN pip install --no-cache-dir -r requirements.txt

# Copy pipeline script
COPY pipeline.py .

# Copy DLT configuration (secrets.toml will be used if environment variables are not set)
COPY .dlt /app/.dlt

# Set Python path
ENV PYTHONPATH=/app

# Run the pipeline
CMD ["python", "pipeline.py"]
