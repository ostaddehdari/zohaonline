#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
[[ -f .env ]] || cp .env.example .env
export DB_ENGINE=sqlite DJANGO_DEBUG=True
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_zoha
.venv/bin/python manage.py runserver 0.0.0.0:8000
