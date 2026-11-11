#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt
[ -f .env ] || ./venv/bin/python configurar.py
./venv/bin/python manage.py instalar_bd
echo "Listo. Ejecute ./iniciar.sh"
