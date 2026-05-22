FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app
COPY data/init.sql /app/data/init.sql
COPY flags.toml /app/flags.toml

# Plant a file readable via fetch_url(file://...) for flag #11.
# Content is rendered from flags.toml at container start by the entrypoint
# so changes to the flag value take effect on `docker compose restart web`.
COPY scripts/render_secret.py /usr/local/bin/render_secret.py
RUN mkdir -p /etc/anvil \
 && chmod +x /usr/local/bin/render_secret.py

# Vendor htmx during the (online) build so the running container can serve it air-gapped.
RUN curl -fsSL https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js \
     -o /app/app/static/htmx.min.js

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "python /usr/local/bin/render_secret.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
