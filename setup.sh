#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
"$PYTHON" -m reel_skill_factory doctor --preinstall
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
echo 'Dependencias instaladas. Configura config.local.json y ejecuta: .venv/bin/python -m reel_skill_factory doctor'
