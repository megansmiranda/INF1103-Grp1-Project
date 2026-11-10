FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=5000 \
    LOG_FILE=/app/logs/nutrilenz.log

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a normal user, not root
RUN useradd --create-home nutrilenz && mkdir -p /app/logs && chown -R nutrilenz /app/logs
USER nutrilenz

EXPOSE 5000
CMD ["python", "main.py"]
