FROM python:3.13-slim

WORKDIR /app

# build-essential covers any package here that doesn't ship a manylinux wheel
# for the current interpreter and needs to compile from source.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Railway injects $PORT at runtime. Migrations run before the server starts
# so every deploy of the web service lands on an up-to-date schema; the
# worker service overrides this CMD with its own start command.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
