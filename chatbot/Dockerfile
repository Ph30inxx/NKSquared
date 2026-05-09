FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc libpq-dev \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files into /app/chatbot to make 'chatbot' an importable package.
# The dashboard/ sub-directory is also copied here and symlinked so it is
# importable as both 'chatbot.dashboard' and 'dashboard'.
COPY . /app/chatbot/

# Make dashboard importable as top-level 'dashboard' package
RUN ln -s /app/chatbot/dashboard /app/dashboard

EXPOSE 8001
CMD ["uvicorn", "chatbot.server:app", "--host", "0.0.0.0", "--port", "8001"]

