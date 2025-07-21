FROM python:3.9.23-slim

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

ENTRYPOINT ["uvicorn", "main:app", "--access-log", "--host", "127.0.0.1", "--port", "8000"]