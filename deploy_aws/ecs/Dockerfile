FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Update pip and install setuptools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY deploy_aws/ecs/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models to avoid runtime download
RUN python -c "import easyocr; reader = easyocr.Reader(['ko', 'en'], gpu=False, download_enabled=True); print('Models downloaded successfully')"

# Copy application code from project root
COPY app/ ./app/
COPY deploy_aws/ecs/processor/ ./processor/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run the processor
CMD ["python", "processor/main.py"]