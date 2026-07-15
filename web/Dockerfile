FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=false \
    DJANGO_DATABASE_PATH=/data/db.sqlite3 \
    DJANGO_MEDIA_ROOT=/data/media \
    DJANGO_STATIC_ROOT=/app/staticfiles \
    SILVERLISTS_ASSET_DIR=/app/assets

WORKDIR /app

RUN addgroup --system silverlists && adduser --system --ingroup silverlists silverlists

COPY web/pyproject.toml web/README.md /app/
COPY web/config /app/config
COPY web/reports /app/reports
COPY web/templates /app/templates
COPY web/report_definitions /app/report_definitions
COPY web/manage.py web/docker-entrypoint.sh /app/
COPY web/assets /app/assets

RUN pip install --no-cache-dir . \
    && chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /data /app/staticfiles \
    && chown -R silverlists:silverlists /app /data

USER silverlists
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --timeout ${GUNICORN_TIMEOUT:-180} --access-logfile -"]
