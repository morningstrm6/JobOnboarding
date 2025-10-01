FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# create a non-root user for safety
RUN adduser --disabled-password --gecos "" appuser || true
USER appuser

EXPOSE 8080

CMD ["python", "bot.py"]
