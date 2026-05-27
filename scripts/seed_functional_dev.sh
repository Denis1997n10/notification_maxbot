#!/usr/bin/env bash
set -euo pipefail
export ENV=dev
python3 backend/src/cli/seed_functional_dev_data.py
