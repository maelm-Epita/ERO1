#!/bin/sh

BASE_DIR="$(pwd)"
VENV="$BASE_DIR/env"

# create venv
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
fi

# deps
"$VENV/bin/pip" install -q -r "$BASE_DIR/requirements.txt"

# activate venv
. "$VENV/bin/activate"
