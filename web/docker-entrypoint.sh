#!/bin/sh
set -eu

mkdir -p "$(dirname "${DJANGO_DATABASE_PATH:-/data/db.sqlite3}")" "${DJANGO_MEDIA_ROOT:-/data/media}"
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
