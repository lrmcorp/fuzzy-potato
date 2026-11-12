FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    ARAH_DATA_DIR=/data ARAH_HOST=0.0.0.0 ARAH_PORT=8787 ARAH_TRUSTED_PROXIES=*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY arah ./arah
RUN pip install . && useradd --create-home --uid 10001 arah && mkdir /data && chown arah:arah /data

USER arah
VOLUME /data
EXPOSE 8787
# Imported from the installed package, not from /app, so the image runs what pip installed.
WORKDIR /home/arah
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/api/session', timeout=4).status == 200 else 1)"
CMD ["arah", "up"]
