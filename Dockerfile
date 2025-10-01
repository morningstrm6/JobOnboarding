FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run will provide PORT, default fallback to 8080
ENV PORT 8080

CMD ["python", "bot.py"]
