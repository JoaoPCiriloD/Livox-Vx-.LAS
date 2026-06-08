#!/usr/bin/env python3
"""
pcd_to_las_ajr.py
=====================

Converte PCD gerado pelo FAST-LIO2 para LAS 1.4.

Suporta PCD ASCII e binary com campos comuns:
  x y z
  x y z intensity
  x y z rgb
  x y z intensity time

O FAST-LIO2 normalmente salva um mapa registrado em PCD. Esse arquivo nao
carrega, por si so, o timestamp original por ponto; quando o campo time existir
ele e preservado como gps_time aproximado. Caso contrario, o LAS sai sem
semantica temporal real, mas pronto para CloudCompare e entrega tecnica.
"""

import argparse
import struct
import sys
from pathlib import Path

try:
    import laspy
    import numpy as np
except ImportError as e:
    print(f"ERRO: biblioteca faltando: {e}")
    print("Instalar com: pip install laspy numpy")
    sys.exit(1)


def parse_header(f):
    header_lines = []
    while True:
        line = f.readline()
        if not line:
            raise ValueError("PCD sem linha DATA")
        text = line.decode("ascii", errors="replace").strip()
        header_lines.append(text)
        if text.startswith("DATA"):
            break

    meta = {}
    for line in header_lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        key = parts[0].upper()
        meta[key] = parts[1:]

    required = ["FIELDS", "SIZE", "TYPE", "COUNT", "WIDTH", "HEIGHT", "POINTS", "DATA"]
    missing = [k for k in required if k not in meta]
    if missing:
        raise ValueError(f"PCD header incompleto: faltando {missing}")

    return meta


def pcd_dtype(meta):
    fields = meta["FIELDS"]
    sizes = [int(v) for v in meta["SIZE"]]
    types = meta["TYPE"]
    counts = [int(v) for v in meta["COUNT"]]

    dtype_fields = []
    for name, size, typ, count in zip(fields, sizes, types, counts):
        if typ == "F" and size == 4:
            base = "<f4"
        elif typ == "F" and size == 8:
            base = "<f8"
        elif typ == "U" and size == 1:
            base = "u1"
        elif typ == "U" and size == 2:
            base = "<u2"
        elif typ == "U" and size == 4:
            base = "<u4"
        elif typ == "I" and size == 1:
            base = "i1"
        elif typ == "I" and size == 2:
            base = "<i2"
        elif typ == "I" and size == 4:
            base = "<i4"
        else:
            raise ValueError(f"Tipo PCD nao suportado: field={name} type={typ} size={size}")

        if count == 1:
            dtype_fields.append((name, base))
        else:
            dtype_fields.append((name, base, (count,)))

    return np.dtype(dtype_fields)


def load_pcd(path):
    path = Path(path)
    with open(path, "rb") as f:
        meta = parse_header(f)
        fields = meta["FIELDS"]
        points = int(meta["POINTS"][0])
        data_kind = meta["DATA"][0].lower()

        if data_kind == "ascii":
            arr = np.loadtxt(f, dtype=np.float64)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            return meta, {name: arr[:, i] for i, name in enumerate(fields)}

        if data_kind != "binary":
            raise ValueError(f"DATA PCD nao suportado: {data_kind}")

        dtype = pcd_dtype(meta)
        arr = np.frombuffer(f.read(points * dtype.itemsize), dtype=dtype, count=points)
        return meta, {name: arr[name] for name in fields}


def rgb_float_to_u16(rgb_values):
    rgb_u32 = rgb_values.astype(np.float32).view(np.uint32)
    r = ((rgb_u32 >> 16) & 255).astype(np.uint16) * 257
    g = ((rgb_u32 >> 8) & 255).astype(np.uint16) * 257
    b = (rgb_u32 & 255).astype(np.uint16) * 257
    return r, g, b


def convert_pcd_to_las(pcd_path, las_path):
    meta, cols = load_pcd(pcd_path)
    for axis in ("x", "y", "z"):
        if axis not in cols:
            raise ValueError(f"PCD sem campo obrigatorio {axis}")

    x = np.asarray(cols["x"], dtype=np.float64)
    y = np.asarray(cols["y"], dtype=np.float64)
    z = np.asarray(cols["z"], dtype=np.float64)
    n = len(x)

    header = laspy.LasHeader(point_format=7, version="1.4")
    header.scales = np.array([0.001, 0.001, 0.001])
    header.offsets = np.array([float(x.min()), float(y.min()), float(z.min())])
    header.global_encoding.gps_time_type = 1

    las = laspy.LasData(header)
    las.x = x
    las.y = y
    las.z = z

    if "intensity" in cols:
        intensity = np.asarray(cols["intensity"], dtype=np.float64)
        if intensity.max() <= 1.0:
            intensity = intensity * 65535.0
        las.intensity = np.clip(intensity, 0, 65535).astype(np.uint16)
    else:
        las.intensity = np.full(n, 1, dtype=np.uint16)

    if "rgb" in cols:
        las.red, las.green, las.blue = rgb_float_to_u16(np.asarray(cols["rgb"]))
    else:
        gray = las.intensity
        las.red = gray
        las.green = gray
        las.blue = gray

    if "time" in cols:
        las.gps_time = np.asarray(cols["time"], dtype=np.float64)
    elif "timestamp" in cols:
        las.gps_time = np.asarray(cols["timestamp"], dtype=np.float64)
    else:
        las.gps_time = np.zeros(n, dtype=np.float64)

    las.write(las_path)
    print(f"LAS gerado: {las_path}")
    print(f"Pontos: {n:,}")
    print(f"Campos PCD: {', '.join(meta['FIELDS'])}")


def main():
    parser = argparse.ArgumentParser(description="Converter PCD FAST-LIO2 para LAS")
    parser.add_argument("pcd")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()
    convert_pcd_to_las(args.pcd, args.output)


if __name__ == "__main__":
    main()
