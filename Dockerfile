FROM python:3.10-slim

# Встановлюємо необхідні бібліотеки, компілятори та системні шрифти
RUN apt-get update && apt-get install -y     gcc     python3-dev     libcairo2-dev     pkg-config     fonts-dejavu-core     build-essential     git     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["python", "main.py"]
