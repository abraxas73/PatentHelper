FROM python:3.12-slim
WORKDIR /srv

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLATFORM=fly

# 한국어 폰트 + PDF 처리 런타임 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
      fonts-noto-cjk fonts-nanum fonts-unfonts-core \
      libjpeg62-turbo zlib1g libfreetype6 libtiff6 liblcms2-2 libwebp7 \
      fontconfig ca-certificates \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

COPY fly/extractor/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# /app 핵심 로직 (cloud-agnostic) 복사
COPY app /srv/app
COPY fly/extractor/worker.py /srv/worker.py

CMD ["python", "-u", "worker.py"]
