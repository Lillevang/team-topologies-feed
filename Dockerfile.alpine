FROM python:3.11-alpine

RUN apk add --no-cache ca-certificates tzdata

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first
COPY requirements.txt .
RUN pip install --disable-pip-version-check --no-cache-dir -r requirements.txt

# App
COPY . .

# Default cache path; mount a volume if you want persistance
ENV CACHE_FILE=/data/cache.json
VOLUME ["/data"]

EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
