# Heavy OCR processing image with PyTorch and EasyOCR
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    fonts-noto-cjk \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-nanum \
    fonts-unfonts-core \
    gcc \
    g++ \
    wget \
    curl \
    fontconfig \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch CPU version first (to avoid large GPU libraries)
RUN pip install --no-cache-dir torch==2.3.0 torchvision==0.18.0 --index-url https://download.pytorch.org/whl/cpu

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models to avoid runtime downloads
RUN python -c "import easyocr; reader = easyocr.Reader(['ko', 'en'], gpu=False, download_enabled=True, verbose=False); print('Models downloaded successfully')"

# Copy application code
COPY app/ ./app/
COPY processor/ ./processor/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# Run the OCR processor
CMD ["python", "-u", "processor/ocr_processor.py"]