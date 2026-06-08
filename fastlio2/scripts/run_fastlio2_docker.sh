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

DOCKER_TTY=()
if [[ -t 0 && -t 1 ]]; then
  DOCKER_TTY=(-it)
fi

docker run --rm "${DOCKER_TTY[@]}" \
  --net=host \
  -v "${ROOT_DIR}:/workspace" \
  -v "$(dirname "${LVX}"):/data:ro" \
  -v "${OUT_DIR}:/out" \
  ajr-fastlio2:noetic \
  bash -lc "/workspace/fastlio2/scripts/run_fastlio2_session.sh --lvx /data/$(basename "${LVX}") --out /out"

echo "Saida: ${OUT_DIR}"
