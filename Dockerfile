FROM python:3.10-slim
RUN apt-get update && apt-get install -y gcc python3-dev libcairo2-dev pkg-config fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir -r requirements.txt
COPY . .
RUN cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /app/DejaVuSans.ttf || true
RUN cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf /app/DejaVuSans-Bold.ttf || true
CMD ["python", "main.py"]
