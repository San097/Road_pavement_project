#!/bin/bash
set -e

echo "Starting Road Pavement Project..."
exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 60 --access-logfile - --error-logfile - app:app
