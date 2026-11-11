#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Abra http://127.0.0.1:8000"
./venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
