FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    libcairo2-dev \
    pkg-config \
    fonts-dejavu-core \
    build-essential \
    git \
    python3-venv \
    libffi-dev \
    libssl-dev \
    cargo \
    rustc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

RUN pip install --upgrade pip pipx && \
    pip install -r requirements.txt

# Ізольоване встановлення maigret
RUN PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install maigret || \
    PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install git+https://github.com/soxoj/maigret.git

COPY . .
RUN mkdir -p reports && chmod 777 reports

ENV PORT=8000
EXPOSE 8000

CMD ["python", "main.py"]
