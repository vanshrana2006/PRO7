#!/usr/bin/env bash
# Runs all offline-testable logic (parser + PDF extraction).
# Once dependencies are installed (pip install -r requirements.txt), this
# also picks up any pytest-based integration tests added in later phases.
set -e
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -p "test_*.py" -v
