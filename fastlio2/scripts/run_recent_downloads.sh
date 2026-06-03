#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_ROOT="${1:-/home/joaop/Downloads}"
OUT_ROOT="${2:-${ROOT_DIR}/fastlio2_output}"

OK=0
FAIL=0
SKIP=0
SUMMARY=()

while IFS= read -r SESSION_DIR; do
  SESSION="$(basename "${SESSION_DIR}")"
  OUT_DIR="${OUT_ROOT}/${SESSION}"

  if [[ -f "${OUT_DIR}/$(find "${SESSION_DIR}" -maxdepth 1 -type f -iname '*.lvx' -printf '%f\n' | sort | tail -n 1 | sed 's/\.lvx$/_fastlio2_map.las/')" ]]; then
    echo "Pulando, LAS ja existe: ${SESSION}"
    SUMMARY+=("${SESSION}: pulado, LAS ja existe")
    SKIP=$((SKIP + 1))
    continue
  fi

  LVX="$(find "${SESSION_DIR}" -maxdepth 1 -type f -iname '*.lvx' -size +1M | sort | tail -n 1 || true)"
  if [[ -z "${LVX}" ]]; then
    echo "Pulando, sem LVX valido: ${SESSION}" >&2
    SUMMARY+=("${SESSION}: pulado, sem LVX valido")
    SKIP=$((SKIP + 1))
    continue
  fi

  echo "============================================================"
  echo "FAST-LIO2: ${SESSION}"
  echo "LVX: ${LVX}"
  echo "============================================================"

  if ! bash "${ROOT_DIR}/fastlio2/scripts/run_fastlio2_docker.sh" "${LVX}" "${OUT_DIR}"; then
    echo "FALHA FAST-LIO2: ${SESSION}" >&2
    SUMMARY+=("${SESSION}: FALHA no FAST-LIO2")
    FAIL=$((FAIL + 1))
    continue
  fi

  PCD="$(find "${OUT_DIR}" -maxdepth 1 -type f -name '*_fastlio2_map.pcd' | sort | tail -n 1 || true)"
  if [[ -z "${PCD}" ]]; then
    echo "FALHA: PCD nao encontrado em ${OUT_DIR}" >&2
    SUMMARY+=("${SESSION}: FALHA, PCD nao encontrado")
    FAIL=$((FAIL + 1))
    continue
  fi

  LAS="${PCD%.pcd}.las"
  if bash "${ROOT_DIR}/fastlio2/scripts/run_pcd_to_las.sh" "${PCD}" "${LAS}"; then
    SUMMARY+=("${SESSION}: OK -> ${LAS}")
    OK=$((OK + 1))
  else
    echo "FALHA conversao PCD->LAS: ${SESSION}" >&2
    SUMMARY+=("${SESSION}: FALHA na conversao PCD->LAS (${PCD})")
    FAIL=$((FAIL + 1))
  fi
done < <(find "${DATA_ROOT}" -maxdepth 1 -type d -name 'voo_20260529_*' | sort)

echo "============================================================"
echo "Resumo FAST-LIO2 downloads recentes"
echo "============================================================"
printf '%s\n' "${SUMMARY[@]}"
echo "OK=${OK} FALHA=${FAIL} PULADO=${SKIP}"

if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
