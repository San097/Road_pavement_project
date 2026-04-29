#!/bin/bash
set -e

# Force Python 3.11.9
export PYENV_VERSION=3.11.9

pip install --upgrade pip
pip install -r requirements.txt
