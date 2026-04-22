FROM python:3.10-slim

RUN apt-get update && apt-get install -y     gcc     python3-dev     libcairo2-dev     pkg-config     fonts-dejavu-core     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Примусове оновлення pip та встановлення fpdf2 в обхід кешу
RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir -r requirements.txt &&     pip install --no-cache-dir fpdf2==2.8.1

# Копіювання шрифтів з ігноруванням помилок, якщо шлях відрізняється
RUN cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /app/DejaVuSans.ttf || true
RUN cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf /app/DejaVuSans-Bold.ttf || true

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["python", "main.py"]
