FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
