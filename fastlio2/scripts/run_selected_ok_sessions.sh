#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_ROOT="${1:-/home/joaop/Downloads}"
OUT_ROOT="${2:-${ROOT_DIR}/fastlio2_output}"

SESSIONS=(
  voo_20260529_161104
  voo_20260529_161231
  voo_20260529_161358
  voo_20260529_161524
  voo_20260529_161652
  voo_20260529_161818
  voo_20260529_161945
  voo_20260529_163248
  voo_20260529_163414
  voo_20260529_163541
  voo_20260529_163708
  voo_20260529_163835
  voo_20260529_164755
  voo_20260529_164921
  voo_20260529_165048
  voo_20260529_165215
  voo_20260529_165342
  voo_20260529_170429
  voo_20260529_170556
  voo_20260529_170723
)

OK=0
FAIL=0
SKIP=0
SUMMARY=()

for SESSION in "${SESSIONS[@]}"; do
  SESSION_DIR="${DATA_ROOT}/${SESSION}"
  OUT_DIR="${OUT_ROOT}/${SESSION}"

  if [[ ! -d "${SESSION_DIR}" ]]; then
    echo "Pulando, pasta nao encontrada: ${SESSION_DIR}" >&2
    SUMMARY+=("${SESSION}: pulado, pasta nao encontrada")
    SKIP=$((SKIP + 1))
    continue
  fi

  if find "${OUT_DIR}" -maxdepth 1 -type f -name '*_fastlio2_map.las' 2>/dev/null | grep -q .; then
    echo "Pulando, LAS FAST-LIO2 ja existe: ${SESSION}"
    SUMMARY+=("${SESSION}: pulado, LAS ja existe")
    SKIP=$((SKIP + 1))
    continue
  fi

  LVX="$(find "${SESSION_DIR}" -maxdepth 1 -type f -iname '*.lvx' -size +1M | sort | tail -n 1 || true)"
  if [[ -z "${LVX}" ]]; then
    echo "Pulando, LVX valido nao encontrado: ${SESSION}" >&2
    SUMMARY+=("${SESSION}: pulado, LVX valido nao encontrado")
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
done

echo "============================================================"
echo "Resumo FAST-LIO2 sessoes selecionadas"
echo "============================================================"
printf '%s\n' "${SUMMARY[@]}"
echo "OK=${OK} FALHA=${FAIL} PULADO=${SKIP}"

if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
