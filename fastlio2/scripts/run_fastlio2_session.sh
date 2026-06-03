#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Uso:
  run_fastlio2_session.sh --lvx ARQUIVO.lvx --out DIR [--config YAML]

Executa:
  LVX -> rosbag via livox_ros_driver
  rosbag -> FAST-LIO2
  FAST-LIO2 -> PCD registrado

Este script deve rodar dentro do container redtech-fastlio2:noetic.
USAGE
}

LVX=""
OUT_DIR=""
CONFIG="/workspace/fastlio2/config/avia_redtech.yaml"
PLAY_RATE="0.5"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lvx) LVX="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --play-rate) PLAY_RATE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento desconhecido: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "${LVX}" || -z "${OUT_DIR}" ]]; then
  usage
  exit 2
fi

if [[ ! -f "${LVX}" ]]; then
  echo "LVX nao encontrado: ${LVX}" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/devel/setup.bash

SESSION_NAME="$(basename "${LVX}" .lvx)"
BAG="${OUT_DIR}/${SESSION_NAME}.bag"
LOG_DIR="${OUT_DIR}/logs"
WORK_DIR="${OUT_DIR}/work"
PCD_DIR="/root/catkin_ws/src/FAST_LIO/PCD"
mkdir -p "${LOG_DIR}" "${WORK_DIR}"
rm -rf "${PCD_DIR}"
mkdir -p "${PCD_DIR}"

echo "==> Copiando config FAST-LIO2"
cp "${CONFIG}" /root/catkin_ws/src/FAST_LIO/config/redtech_avia.yaml
cp "${CONFIG}" /root/catkin_ws/src/FAST_LIO/config/avia.yaml

echo "==> Convertendo LVX para rosbag"
BEFORE_BAGS="${LOG_DIR}/bags_before.txt"
AFTER_BAGS="${LOG_DIR}/bags_after.txt"
LOCAL_LVX="${WORK_DIR}/$(basename "${LVX}")"
if [[ "${LVX}" != "${LOCAL_LVX}" ]]; then
  cp -f "${LVX}" "${LOCAL_LVX}"
fi
find /data "${OUT_DIR}" /root -maxdepth 3 -type f -name '*.bag' 2>/dev/null | sort > "${BEFORE_BAGS}" || true
pushd "${WORK_DIR}" >/dev/null

set +e
roslaunch livox_ros_driver lvx_to_rosbag.launch \
  lvx_file_path:="${LOCAL_LVX}" \
  xfer_format:=1 \
  publish_freq:=10.0 \
  rosbag_enable:=true \
  lidar_bag:=true \
  imu_bag:=true \
  rviz_enable:=false \
  > "${LOG_DIR}/lvx_to_rosbag.log" 2>&1 &
LVX_LAUNCH_PID=$!

LAST_BAG_SIZE=-1
BAG_STABLE_COUNT=0
for _ in $(seq 1 1800); do
  if grep -q "Save the bag file successfully" "${LOG_DIR}/lvx_to_rosbag.log" 2>/dev/null; then
    break
  fi
  CURRENT_BAG="$(find "${WORK_DIR}" -maxdepth 1 -type f -name '*.bag' -printf '%s %p\n' 2>/dev/null | sort -n | tail -n 1 || true)"
  if [[ -n "${CURRENT_BAG}" ]]; then
    CURRENT_BAG_SIZE="${CURRENT_BAG%% *}"
    if [[ "${CURRENT_BAG_SIZE}" -gt 1048576 && "${CURRENT_BAG_SIZE}" -eq "${LAST_BAG_SIZE}" ]]; then
      BAG_STABLE_COUNT=$((BAG_STABLE_COUNT + 1))
    else
      BAG_STABLE_COUNT=0
      LAST_BAG_SIZE="${CURRENT_BAG_SIZE}"
    fi
    if [[ "${BAG_STABLE_COUNT}" -ge 8 ]]; then
      break
    fi
  fi
  if ! kill -0 "${LVX_LAUNCH_PID}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if kill -0 "${LVX_LAUNCH_PID}" >/dev/null 2>&1; then
  kill -INT "${LVX_LAUNCH_PID}" >/dev/null 2>&1
  sleep 3
fi
if kill -0 "${LVX_LAUNCH_PID}" >/dev/null 2>&1; then
  kill "${LVX_LAUNCH_PID}" >/dev/null 2>&1
fi
wait "${LVX_LAUNCH_PID}"
LVX_STATUS=$?
set -e
popd >/dev/null

find /data "${OUT_DIR}" /root -maxdepth 4 -type f -name '*.bag' 2>/dev/null | sort > "${AFTER_BAGS}" || true
FOUND_BAG="$(
  find "${WORK_DIR}" "${OUT_DIR}" /root -maxdepth 4 -type f -name '*.bag' -size +1M -printf '%s %p\n' 2>/dev/null \
    | sort -n \
    | tail -n 1 \
    | cut -d' ' -f2-
)"
if [[ -z "${FOUND_BAG}" ]]; then
  echo "Nenhum .bag gerado pelo livox_ros_driver. Veja ${LOG_DIR}/lvx_to_rosbag.log e ${AFTER_BAGS}" >&2
  exit 1
fi
if [[ "${LVX_STATUS}" -ne 0 ]] && ! grep -q "Save the bag file successfully" "${LOG_DIR}/lvx_to_rosbag.log" 2>/dev/null; then
  echo "Falha na conversao LVX->rosbag. Veja ${LOG_DIR}/lvx_to_rosbag.log" >&2
  exit 1
fi
cp "${FOUND_BAG}" "${BAG}"
echo "Rosbag: ${BAG}"
rosbag info "${BAG}" > "${LOG_DIR}/rosbag_info.log" 2>&1 || true

echo "==> Iniciando roscore"
roscore > "${LOG_DIR}/roscore.log" 2>&1 &
ROSCORE_PID=$!
sleep 4

cleanup() {
  set +e
  if [[ -n "${FASTLIO_PID:-}" ]] && kill -0 "${FASTLIO_PID}" >/dev/null 2>&1; then
    kill -INT "${FASTLIO_PID}" >/dev/null 2>&1
    wait "${FASTLIO_PID}" >/dev/null 2>&1
  fi
  if [[ -n "${ROSCORE_PID:-}" ]] && kill -0 "${ROSCORE_PID}" >/dev/null 2>&1; then
    kill -INT "${ROSCORE_PID}" >/dev/null 2>&1
    wait "${ROSCORE_PID}" >/dev/null 2>&1
  fi
}
trap cleanup EXIT

echo "==> Iniciando FAST-LIO2"
export QT_QPA_PLATFORM=offscreen
roslaunch fast_lio mapping_avia.launch \
  config_file:=redtech_avia.yaml \
  rviz:=false \
  > "${LOG_DIR}/fastlio2.log" 2>&1 &
FASTLIO_PID=$!
sleep 5

echo "==> Tocando rosbag"
rosbag play "${BAG}" --clock -r "${PLAY_RATE}" --quiet > "${LOG_DIR}/rosbag_play.log" 2>&1
sleep 20

echo "==> Encerrando FAST-LIO2"
cleanup
trap - EXIT

PCD="$(find "${PCD_DIR}" -type f -name '*.pcd' | sort | tail -n 1 || true)"
if [[ -z "${PCD}" ]]; then
  echo "FAST-LIO2 nao gerou PCD. Veja ${LOG_DIR}/fastlio2.log" >&2
  exit 1
fi

OUT_PCD="${OUT_DIR}/${SESSION_NAME}_fastlio2_map.pcd"
cp "${PCD}" "${OUT_PCD}"
echo "PCD FAST-LIO2: ${OUT_PCD}"
