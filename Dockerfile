FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=run.py

# mariadb Python connector links against libmariadb at build + runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# gevent worker class: good for the I/O-heavy mix here (Redis, OpenAI, Stripe).
# Note: the mariadb connector is a C extension and won't yield under gevent —
# DB calls still work, they just block the greenlet.
CMD ["gunicorn", \
     "-k", "gevent", \
     "-w", "4", \
     "--worker-connections", "1000", \
     "-b", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "run:app"]
