FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files into /app/chatbot to make 'chatbot' an importable package
COPY . /app/chatbot/

EXPOSE 8001
CMD ["uvicorn", "chatbot.server:app", "--host", "0.0.0.0", "--port", "8001"]

