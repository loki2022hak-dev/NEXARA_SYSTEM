FROM python:3.10-slim
RUN apt-get update && apt-get install -y gcc python3-dev fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt &&     pip install --upgrade typing-extensions>=4.11.0
COPY . .
RUN mkdir -p reports
CMD ["python", "main.py"]
