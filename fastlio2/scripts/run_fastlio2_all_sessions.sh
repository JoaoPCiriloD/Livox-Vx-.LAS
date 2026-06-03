#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_ROOT="${1:-/home/joaop/Downloads/drive-download-20260601T172413Z-3-002}"
OUT_ROOT="${2:-${ROOT_DIR}/fastlio2_output}"

LVX_FILES=(
  "${DATA_ROOT}/voo_20260529_125507/lidar_2026-05-29T12-55-07Z.lvx"
  "${DATA_ROOT}/voo_20260529_161358/lidar_2026-05-29T16-13-58Z.lvx"
  "${DATA_ROOT}/voo_20260529_161524/lidar_2026-05-29T16-15-24Z.lvx"
  "${DATA_ROOT}/voo_20260529_161652/lidar_2026-05-29T16-16-52Z.lvx"
)

OK=0
FAIL=0
SUMMARY=()

for LVX in "${LVX_FILES[@]}"; do
  if [[ ! -f "${LVX}" ]]; then
    echo "Pulando, LVX nao encontrado: ${LVX}" >&2
    continue
  fi

  SESSION="$(basename "$(dirname "${LVX}")")"
  OUT_DIR="${OUT_ROOT}/${SESSION}"
  echo "============================================================"
  echo "FAST-LIO2: ${SESSION}"
  echo "============================================================"
  if ! bash "${ROOT_DIR}/fastlio2/scripts/run_fastlio2_docker.sh" "${LVX}" "${OUT_DIR}"; then
    echo "FALHA FAST-LIO2: ${SESSION}" >&2
    SUMMARY+=("${SESSION}: FALHA no FAST-LIO2")
    FAIL=$((FAIL + 1))
    continue
  fi

  PCD="$(find "${OUT_DIR}" -maxdepth 1 -type f -name '*_fastlio2_map.pcd' | sort | tail -n 1 || true)"
  if [[ -n "${PCD}" ]]; then
    LAS="${PCD%.pcd}.las"
    if bash "${ROOT_DIR}/fastlio2/scripts/run_pcd_to_las.sh" "${PCD}" "${LAS}"; then
      SUMMARY+=("${SESSION}: OK -> ${LAS}")
      OK=$((OK + 1))
    else
      echo "FALHA conversao PCD->LAS: ${SESSION}" >&2
      SUMMARY+=("${SESSION}: FALHA na conversao PCD->LAS (${PCD})")
      FAIL=$((FAIL + 1))
    fi
  else
    echo "FALHA: PCD nao encontrado em ${OUT_DIR}" >&2
    SUMMARY+=("${SESSION}: FALHA, PCD nao encontrado")
    FAIL=$((FAIL + 1))
  fi
done

echo "============================================================"
echo "Resumo FAST-LIO2"
echo "============================================================"
printf '%s\n' "${SUMMARY[@]}"
echo "OK=${OK} FALHA=${FAIL}"

if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
