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
    pipx \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# CORE ENV (фікс dependency graph)
RUN pip install --upgrade pip setuptools wheel && \
    pip install "typing-extensions>=4.11,<5" && \
    pip install --no-cache-dir -r requirements.txt

# ISOLATED OSINT TOOL (повністю поза pip dependency tree)
RUN PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install maigret==0.4.4 --force

COPY . .

RUN mkdir -p reports && chmod 777 reports

ENV PORT=8000
EXPOSE 8000

CMD ["python", "main.py"]
