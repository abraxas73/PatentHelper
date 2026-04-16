FROM python:3.12-slim
WORKDIR /srv

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLATFORM=fly \
    TORCH_HOME=/srv/.torch \
    EASYOCR_MODULE_PATH=/srv/.easyocr

RUN apt-get update && apt-get install -y --no-install-recommends \
      fonts-noto-cjk fonts-nanum fonts-unfonts-core \
      libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
      libjpeg62-turbo zlib1g libfreetype6 libtiff6 liblcms2-2 libwebp7 \
      fontconfig ca-certificates \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

# PyTorch CPU만 먼저 (용량 최적 + 캐시 분리)
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
      torch==2.3.0 torchvision==0.18.0

COPY fly/ocr/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# EasyOCR 모델 사전 다운로드 (콜드스타트 절감)
RUN python -c "import easyocr; easyocr.Reader(['ko','en'], gpu=False, model_storage_directory='/srv/.easyocr', download_enabled=True)"

COPY app /srv/app
COPY fly/ocr/worker.py /srv/worker.py

CMD ["python", "-u", "worker.py"]
