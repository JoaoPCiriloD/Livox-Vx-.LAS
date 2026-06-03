#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Uso: $0 mapa_fastlio2.pcd saida.las" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
"${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/pcd_to_las_redtech.py" "$1" -o "$2"
