FROM python:3.12-slim

RUN apt-get update && apt-get install -y git libpq-dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY . /app

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/src

CMD ["python", "-u", "main.py"]
