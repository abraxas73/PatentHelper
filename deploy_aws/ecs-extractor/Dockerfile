# Lightweight image for mapping extraction (no OCR)
FROM python:3.12-slim

# Install system dependencies for PDF processing only
RUN apt-get update && apt-get install -y \
    # Basic image processing
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Image format support
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    # Korean fonts for text rendering
    fonts-noto-cjk \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-nanum \
    fonts-unfonts-core \
    # Build tools
    gcc \
    g++ \
    wget \
    curl \
    fontconfig \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install lightweight Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY processor/extractor.py ./processor/extractor.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# Run the extractor
CMD ["python", "-u", "processor/extractor.py"]
# Force rebuild Fri Sep 19 13:44:37 KST 2025
