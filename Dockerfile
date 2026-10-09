FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV NUTRILENZ_DATA_DIR=/app/data

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
