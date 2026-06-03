#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: $0 ARQUIVO.lvx [OUT_DIR]" >&2
  exit 2
fi

LVX="$(realpath "$1")"
OUT_DIR="${2:-$(pwd)/fastlio2_output/$(basename "${LVX}" .lvx)}"
OUT_DIR="$(realpath -m "${OUT_DIR}")"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p "${OUT_DIR}"

docker run --rm -it \
  --net=host \
  -v "${ROOT_DIR}:/workspace" \
  -v "$(dirname "${LVX}"):/data:ro" \
  -v "${OUT_DIR}:/out" \
  redtech-fastlio2:noetic \
  bash -lc "/workspace/fastlio2/scripts/run_fastlio2_session.sh --lvx /data/$(basename "${LVX}") --out /out"

echo "Saida: ${OUT_DIR}"
