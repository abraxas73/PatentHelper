FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # OpenCV dependencies
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Pillow dependencies
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    # Unicode fonts (Noto Sans CJK, DejaVu Sans, Liberation fonts)
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-liberation \
    fonts-liberation2 \
    # Korean fonts
    fonts-nanum \
    fonts-nanum-coding \
    fonts-nanum-extra \
    fonts-unfonts-core \
    # Build tools
    gcc \
    g++ \
    # Utils
    wget \
    curl \
    fontconfig \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Update pip and install setuptools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY deploy_aws/ecs/requirements.txt .

# Install CPU-only torch first (smaller size for ECS)
RUN pip install --no-cache-dir torch==2.3.0 torchvision==0.18.0 --index-url https://download.pytorch.org/whl/cpu

# Install other Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models to avoid runtime download
# Also configure for better CPU performance
RUN python -c "import easyocr; reader = easyocr.Reader(['ko', 'en'], gpu=False, download_enabled=True, verbose=False); print('Models downloaded successfully')"

# Set environment variables for CPU optimization
ENV OMP_NUM_THREADS=4
ENV MKL_NUM_THREADS=4
ENV NUMEXPR_NUM_THREADS=4

# Copy application code from project root
COPY app/ ./app/
COPY deploy_aws/ecs/processor/ ./processor/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run the processor
CMD ["python", "processor/main.py"]