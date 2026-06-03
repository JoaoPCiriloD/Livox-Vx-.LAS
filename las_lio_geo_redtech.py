#!/usr/bin/env python3
"""
las_lio_geo_redtech.py v0.1
===========================

Georreferencia um LAS local considerando odometria inercial extraida do LVX.

Este modulo implementa uma reconstrucao inercial pratica:
  1. extrai IMU do LVX (gyro_xyz + acc_xyz),
  2. estima bias inicial do giroscopio,
  3. integra gyro para obter roll/pitch/yaw ao longo do tempo,
  4. interpola a orientacao para cada ponto LAS,
  5. rotaciona os pontos locais antes de aplicar a translacao GNSS/UTM.

Limite importante: isto ainda nao e um SLAM LIO completo como FAST-LIO ou
LIO-SAM, pois nao faz scan matching/ICP nem otimizacao em grafo. E uma etapa
intermediaria que usa a odometria inercial disponivel no LVX para corrigir a
orientacao por tempo antes do georreferenciamento.
"""

import argparse
import copy
import csv
import math
import struct
import sys
from pathlib import Path
from datetime import datetime, timezone

try:
    import laspy
    import numpy as np
    import pyproj
except ImportError as e:
    print(f"ERRO: biblioteca faltando: {e}")
    print("Instalar com: pip install laspy numpy pyproj pyubx2")
    sys.exit(1)

from las_geo_redtech import extract_trajectory, gps_adjusted_to_unix


PACKAGE_HEADER_SIZE = 19
POINT_PAYLOAD_SIZES = {
    0: 100 * 13,
    1: 100 * 9,
    2: 96 * 14,
    3: 96 * 10,
    4: 48 * 28,
    5: 48 * 20,
    6: 1 * 24,
    7: 32 * 42,
    8: 32 * 30,
}


def timestamp_unix_from_pkg(pkg_bytes):
    ts_type = pkg_bytes[9]
    if ts_type != 3:
        return None
    year = pkg_bytes[11]
    month = pkg_bytes[12]
    day = pkg_bytes[13]
    hour = pkg_bytes[14]
    us_within_hour = struct.unpack("<I", pkg_bytes[15:19])[0]
    try:
        full_year = 2000 + year if year < 100 else year
        dt = datetime(full_year, month, day, hour, 0, 0, tzinfo=timezone.utc)
    except ValueError:
        return None
    return dt.timestamp() + us_within_hour / 1e6


def extract_lvx_imu(lvx_path, verbose=True):
    """Extrai amostras IMU do LVX como arrays: t_unix, gyro, acc."""
    lvx_path = Path(lvx_path)
    times = []
    gyros = []
    accs = []

    with open(lvx_path, "rb") as f:
        sig = f.read(16)
        if not sig.startswith(b"livox_tech") and verbose:
            print(f"  AVISO: assinatura LVX inesperada: {sig[:10]}")
        f.seek(24)
        frame_duration = struct.unpack("<I", f.read(4))[0]
        device_count = struct.unpack("<B", f.read(1))[0]
        f.seek(device_count * 59, 1)

        file_size = lvx_path.stat().st_size
        current_pos = f.tell()

        while current_pos < file_size:
            f.seek(current_pos)
            fhdr = f.read(24)
            if len(fhdr) < 24:
                break
            next_offset = struct.unpack("<Q", fhdr[8:16])[0]
            if next_offset <= current_pos or next_offset > file_size:
                break

            bytes_remaining = next_offset - (current_pos + 24)
            while bytes_remaining >= PACKAGE_HEADER_SIZE:
                pkg = f.read(PACKAGE_HEADER_SIZE)
                if len(pkg) < PACKAGE_HEADER_SIZE:
                    break

                data_type = pkg[10]
                bytes_remaining -= PACKAGE_HEADER_SIZE
                payload_size = POINT_PAYLOAD_SIZES.get(data_type)
                if payload_size is None or bytes_remaining < payload_size:
                    break

                payload = f.read(payload_size)
                bytes_remaining -= payload_size

                if data_type != 6:
                    continue
                t_unix = timestamp_unix_from_pkg(pkg)
                if t_unix is None:
                    continue
                gx, gy, gz, ax, ay, az = struct.unpack("<ffffff", payload)
                times.append(t_unix)
                gyros.append((gx, gy, gz))
                accs.append((ax, ay, az))

            current_pos = next_offset

    if len(times) < 2:
        raise ValueError(f"IMU insuficiente no LVX: {len(times)} amostras")

    t = np.asarray(times, dtype=np.float64)
    order = np.argsort(t)
    gyro = np.asarray(gyros, dtype=np.float64)[order]
    acc = np.asarray(accs, dtype=np.float64)[order]
    t = t[order]

    if verbose:
        duration = t[-1] - t[0]
        rate = len(t) / duration if duration > 0 else 0
        print(f"  IMU: {len(t):,} amostras, {duration:.2f}s, {rate:.1f} Hz")
        print(f"  Frame duration LVX: {frame_duration} ms")

    return {"t_unix": t, "gyro": gyro, "acc": acc}


def integrate_gyro_euler(imu, bias_seconds=2.0, gyro_scale=1.0, verbose=True):
    """
    Integra gyro em rad/s para roll/pitch/yaw.

    A estimativa e deliberadamente simples e deterministica. Remove bias pelo
    valor mediano inicial e integra cada eixo no tempo da IMU.
    """
    t = imu["t_unix"]
    gyro = imu["gyro"].copy() * gyro_scale

    bias_mask = t <= (t[0] + bias_seconds)
    if np.count_nonzero(bias_mask) < 10:
        bias_mask = np.arange(len(t)) < min(200, len(t))
    bias = np.median(gyro[bias_mask], axis=0)
    gyro -= bias

    dt = np.diff(t, prepend=t[0])
    dt = np.clip(dt, 0.0, 0.05)

    angles = np.cumsum(gyro * dt[:, None], axis=0)
    # Remove orientacao inicial para manter a nuvem no referencial local inicial.
    angles -= angles[0]

    if verbose:
        span_deg = np.degrees(angles.max(axis=0) - angles.min(axis=0))
        print(f"  Escala gyro aplicada: {gyro_scale:.9g}")
        print(f"  Bias gyro removido (rad/s apos escala): "
              f"{bias[0]:+.5f}, {bias[1]:+.5f}, {bias[2]:+.5f}")
        print(f"  Variacao integrada R/P/Y: "
              f"{span_deg[0]:.1f}/{span_deg[1]:.1f}/{span_deg[2]:.1f} deg")

    return {
        "t_unix": t,
        "roll": angles[:, 0],
        "pitch": angles[:, 1],
        "yaw": angles[:, 2],
        "gyro_bias": bias,
    }


def rotate_xyz_euler(xs, ys, zs, roll, pitch, yaw):
    """
    Aplica Rz(yaw) * Ry(pitch) * Rx(roll) em arrays.
    """
    cr = np.cos(roll); sr = np.sin(roll)
    cp = np.cos(pitch); sp = np.sin(pitch)
    cy = np.cos(yaw); sy = np.sin(yaw)

    # Rx
    x1 = xs
    y1 = cr * ys - sr * zs
    z1 = sr * ys + cr * zs
    # Ry
    x2 = cp * x1 + sp * z1
    y2 = y1
    z2 = -sp * x1 + cp * z1
    # Rz
    x3 = cy * x2 - sy * y2
    y3 = sy * x2 + cy * y2
    z3 = z2
    return x3, y3, z3


def write_trajectory_csv(path, orientation, traj_utm):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "t_unix", "utm_x", "utm_y", "alt_m",
            "roll_deg", "pitch_deg", "yaw_deg",
        ])
        t = orientation["t_unix"]
        x = np.interp(t, traj_utm["t_unix"], traj_utm["x"])
        y = np.interp(t, traj_utm["t_unix"], traj_utm["y"])
        z = np.interp(t, traj_utm["t_unix"], traj_utm["z"])
        for row in zip(
            t, x, y, z,
            np.degrees(orientation["roll"]),
            np.degrees(orientation["pitch"]),
            np.degrees(orientation["yaw"]),
        ):
            writer.writerow([f"{v:.9f}" for v in row])


def lio_georeference_las(las_path, ubx_path, lvx_path, output_path,
                         trajectory_csv, utm_zone, hemisphere,
                         chunk_size=1_000_000, gyro_scale=1.0, verbose=True):
    las_path = Path(las_path)
    output_path = Path(output_path)

    if verbose:
        print("Extraindo trajetoria GNSS...")
    traj = extract_trajectory(str(ubx_path), verbose=verbose)

    if verbose:
        print("\nExtraindo e integrando IMU do LVX...")
    imu = extract_lvx_imu(lvx_path, verbose=verbose)
    orientation = integrate_gyro_euler(imu, gyro_scale=gyro_scale, verbose=verbose)

    wgs84 = pyproj.CRS("EPSG:4326")
    utm = pyproj.CRS(f"EPSG:{327 if hemisphere == 'south' else 326}{utm_zone:02d}")
    transformer = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True)
    traj_x, traj_y = transformer.transform(traj["lon"], traj["lat"])
    traj_utm = {
        "t_unix": traj["t_unix"],
        "x": np.asarray(traj_x, dtype=np.float64),
        "y": np.asarray(traj_y, dtype=np.float64),
        "z": np.asarray(traj["alt"], dtype=np.float64),
    }

    if trajectory_csv:
        write_trajectory_csv(trajectory_csv, orientation, traj_utm)
        if verbose:
            print(f"  Trajetoria LIO CSV: {trajectory_csv}")

    with laspy.open(str(las_path)) as reader:
        in_header = reader.header
        if in_header.point_format.id != 3:
            raise ValueError(
                f"LAS input Point Format {in_header.point_format.id}; esperado 3"
            )

        # Estima offsets globais sem carregar todos os pontos.
        x_offset = float(np.min(traj_utm["x"]) + in_header.mins[0] - 20.0)
        y_offset = float(np.min(traj_utm["y"]) + in_header.mins[1] - 20.0)
        z_offset = float(np.min(traj_utm["z"]) + in_header.mins[2] - 20.0)

        out_header = laspy.LasHeader(point_format=3, version="1.2")
        out_header.global_encoding.gps_time_type = 1
        out_header.scales = np.array([0.001, 0.001, 0.001])
        out_header.offsets = np.array([x_offset, y_offset, z_offset])

        total = reader.header.point_count
        if verbose:
            print(f"\nAplicando orientacao LIO em chunks: {total:,} pontos")
            print(f"  Output: {output_path}")

        with laspy.open(str(output_path), mode="w", header=out_header) as writer:
            processed = 0
            for points in reader.chunk_iterator(chunk_size):
                chunk = laspy.LasData(copy.deepcopy(in_header))
                chunk.points = points

                t_unix = gps_adjusted_to_unix(chunk.gps_time)
                t_gnss = np.clip(
                    t_unix, traj_utm["t_unix"].min(), traj_utm["t_unix"].max()
                )
                t_imu = np.clip(
                    t_unix,
                    orientation["t_unix"].min(),
                    orientation["t_unix"].max(),
                )

                drone_x = np.interp(t_gnss, traj_utm["t_unix"], traj_utm["x"])
                drone_y = np.interp(t_gnss, traj_utm["t_unix"], traj_utm["y"])
                drone_z = np.interp(t_gnss, traj_utm["t_unix"], traj_utm["z"])

                roll = np.interp(t_imu, orientation["t_unix"], orientation["roll"])
                pitch = np.interp(t_imu, orientation["t_unix"], orientation["pitch"])
                yaw = np.interp(t_imu, orientation["t_unix"], orientation["yaw"])

                local_x = np.asarray(chunk.x, dtype=np.float64)
                local_y = np.asarray(chunk.y, dtype=np.float64)
                local_z = np.asarray(chunk.z, dtype=np.float64)
                rx, ry, rz = rotate_xyz_euler(
                    local_x, local_y, local_z, roll, pitch, yaw
                )

                out = laspy.LasData(out_header)
                out.x = drone_x + rx
                out.y = drone_y + ry
                out.z = drone_z + rz
                out.intensity = chunk.intensity
                out.gps_time = chunk.gps_time
                out.red = chunk.red
                out.green = chunk.green
                out.blue = chunk.blue
                writer.write_points(out.points)

                processed += len(points)
                if verbose:
                    print(f"  {processed:,}/{total:,} pontos", end="\r")

    if verbose:
        print()
        print(f"Arquivo LIO salvo: {output_path}")
        print(f"Tamanho: {output_path.stat().st_size / 1e6:.1f} MB")

    return {
        "imu_samples": len(orientation["t_unix"]),
        "gyro_bias": orientation["gyro_bias"].tolist(),
        "roll_span_deg": float(np.degrees(
            orientation["roll"].max() - orientation["roll"].min()
        )),
        "pitch_span_deg": float(np.degrees(
            orientation["pitch"].max() - orientation["pitch"].min()
        )),
        "yaw_span_deg": float(np.degrees(
            orientation["yaw"].max() - orientation["yaw"].min()
        )),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Georreferencia LAS usando GNSS + orientacao IMU do LVX"
    )
    parser.add_argument("las")
    parser.add_argument("ubx")
    parser.add_argument("lvx")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--trajectory-csv", default=None)
    parser.add_argument("--utm-zone", type=int, default=22)
    parser.add_argument("--hemisphere", choices=["south", "north"], default="south")
    parser.add_argument("--chunk-size", type=int, default=1_000_000)
    parser.add_argument(
        "--gyro-scale",
        type=float,
        default=1.0,
        help="Escala aplicada ao gyro do LVX antes da integracao. Use 0.01745329252 se o gyro estiver em graus/s.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    lio_georeference_las(
        args.las,
        args.ubx,
        args.lvx,
        args.output,
        args.trajectory_csv,
        args.utm_zone,
        args.hemisphere,
        args.chunk_size,
        args.gyro_scale,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
