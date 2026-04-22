FROM python:3.10-slim
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libcairo2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000
EXPOSE 8000
CMD ["python", "main.py"]
