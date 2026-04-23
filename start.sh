#!/bin/bash
gunicorn --bind 0.0.0.0:$PORT --workers ${WEB_CONCURRENCY:-1} road_pavement_project.app:app
