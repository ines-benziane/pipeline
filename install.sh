#!/usr/bin/env bash
# Active l'environnement conda cible avant de lancer ce script.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing myo-pipeline workspace..."

(cd "${SCRIPT_DIR}" && pip install -e ".[dev]")
pip install -e "${SCRIPT_DIR}/medical_report"
pip install -e "${SCRIPT_DIR}/medical_report/src/medical_report/tools/py-bspline"

echo "myo-pipeline workspace installed successfully."
