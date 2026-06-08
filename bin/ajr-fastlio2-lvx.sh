#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Uso:
  bin/ajr-fastlio2-lvx.sh ARQUIVO.lvx [OUT_DIR]

Executa o fluxo completo:
  LVX -> ROS bag -> FAST-LIO2 -> PCD -> LAS

Exemplo:
  bin/ajr-fastlio2-lvx.sh /home/joao/Downloads/voo/lidar.lvx fastlio2_output/voo
USAGE
}

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LVX="$(realpath "$1")"
OUT_DIR="${2:-${ROOT_DIR}/fastlio2_output/$(basename "${LVX}" .lvx)}"
OUT_DIR="$(realpath -m "${OUT_DIR}")"

if [[ ! -f "${LVX}" ]]; then
  echo "LVX nao encontrado: ${LVX}" >&2
  exit 1
fi

if [[ ! -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  echo "==> Criando ambiente Python local"
  python3 -m venv "${ROOT_DIR}/.venv"
fi

echo "==> Instalando/validando dependencias Python"
"${ROOT_DIR}/.venv/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt"

if ! docker image inspect ajr-fastlio2:noetic >/dev/null 2>&1; then
  echo "==> Imagem Docker ajr-fastlio2:noetic nao encontrada; construindo"
  bash "${ROOT_DIR}/fastlio2/scripts/build_fastlio2_docker.sh"
fi

echo "==> Executando FAST-LIO2"
bash "${ROOT_DIR}/fastlio2/scripts/run_fastlio2_docker.sh" "${LVX}" "${OUT_DIR}"

PCD="$(find "${OUT_DIR}" -maxdepth 1 -type f -name '*_fastlio2_map.pcd' | sort | tail -n 1 || true)"
if [[ -z "${PCD}" ]]; then
  echo "PCD nao encontrado em ${OUT_DIR}. Verifique ${OUT_DIR}/logs/fastlio2.log" >&2
  exit 1
fi

LAS="${PCD%.pcd}.las"
echo "==> Convertendo PCD para LAS"
bash "${ROOT_DIR}/fastlio2/scripts/run_pcd_to_las.sh" "${PCD}" "${LAS}"

echo "Concluido"
echo "PCD: ${PCD}"
echo "LAS: ${LAS}"
