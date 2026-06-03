#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

docker build \
  -t redtech-fastlio2:noetic \
  -f "${ROOT_DIR}/fastlio2/docker/Dockerfile.noetic" \
  "${ROOT_DIR}/fastlio2/docker"

echo "Imagem criada: redtech-fastlio2:noetic"
