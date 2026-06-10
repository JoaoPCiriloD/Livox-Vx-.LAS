#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Uso: $0 mapa_fastlio2.pcd saida.las" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv-wsl/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "ERRO: ambiente .venv-wsl nao encontrado." >&2
  echo "Execute bin/ajr-fastlio2-lvx.sh ou crie o ambiente conforme o README." >&2
  exit 127
fi
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/converters/pcd_to_las_ajr.py" "$1" -o "$2"
