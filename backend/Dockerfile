# Budowany z katalogu glownego repo (context: .), bo obraz zawiera tez frontend.
# Obraz wieloarchitekturowy (amd64, arm64) budowany przez .github/workflows/release.yml.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Kod nalezy do roota (proces aplikacji nie moze go zmienic); zapisywalny jest tylko /data.
# Aplikacja dziala jako PUID:PGID (domyslnie 1000:1000) - docker-entrypoint.sh ustawia wlasciciela /data
# i porzuca uprawnienia roota przed startem (setpriv).
COPY backend/app ./app
COPY frontend ./frontend
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN mkdir -p /data

ENV PUID=1000 \
    PGID=1000

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
