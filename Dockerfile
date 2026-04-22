FROM python:3.10-slim

# Встановлення системних залежностей, компіляторів та шрифтів з підтримкою UTF-8
RUN apt-get update && apt-get install -y     gcc     python3-dev     libcairo2-dev     pkg-config     fonts-dejavu-core     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо системний шрифт у робочу директорію для fpdf2
RUN cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /app/DejaVuSans.ttf
RUN cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf /app/DejaVuSans-Bold.ttf

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["python", "main.py"]
