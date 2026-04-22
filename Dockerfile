FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libcairo2-dev \
    pkg-config \
    fonts-dejavu-core \
    build-essential \
    git \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip pipx && \
    pip install --no-cache-dir -r requirements.txt

RUN PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install maigret==0.4.4

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["python", "main.py"]
