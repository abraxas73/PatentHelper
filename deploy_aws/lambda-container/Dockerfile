# Lambda container image for OCR processing
FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies (smaller set for Lambda)
RUN dnf install -y \
    mesa-libGL \
    glib2 \
    zlib-devel \
    libjpeg-devel \
    gcc \
    python3-devel \
    && dnf clean all

# Install Python packages (optimized for Lambda)
# First install CPU-only torch to avoid downloading CUDA dependencies
RUN pip install --no-cache-dir \
    torch==2.3.0 torchvision==0.18.0 --index-url https://download.pytorch.org/whl/cpu \
    --target "${LAMBDA_TASK_ROOT}"

# Install dependencies for easyocr without reinstalling torch
RUN pip install --no-cache-dir \
    pypdfium2==4.25.0 \
    pillow==9.5.0 \
    numpy==1.26.0 \
    opencv-python-headless==4.10.0.84 \
    scipy \
    scikit-image \
    python-bidi \
    PyYAML \
    Shapely \
    pyclipper \
    ninja \
    --target "${LAMBDA_TASK_ROOT}"

# Install easyocr without dependencies to avoid reinstalling torch
RUN pip install --no-cache-dir --no-deps \
    easyocr==1.7.0 \
    --target "${LAMBDA_TASK_ROOT}"

# Pre-download OCR models
RUN python -c "import sys; sys.path.insert(0, '${LAMBDA_TASK_ROOT}'); import easyocr; reader = easyocr.Reader(['ko', 'en'], gpu=False, download_enabled=True, verbose=False)"

# Copy function code
COPY handler.py ${LAMBDA_TASK_ROOT}
COPY app/ ${LAMBDA_TASK_ROOT}/app/

# Set the CMD to your handler
CMD [ "handler.lambda_handler" ]