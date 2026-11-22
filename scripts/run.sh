#!/bin/sh
# Start the dashboard (Linux / macOS). Windows: use scripts/run.bat
cd "$(dirname "$0")/.."
python3 -m factory.server
