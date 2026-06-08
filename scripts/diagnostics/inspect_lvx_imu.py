#!/usr/bin/env python3
import argparse
import struct
from pathlib import Path
from datetime import datetime, timezone

PACKAGE_HEADER_SIZE = 19


def timestamp_unix(pkg_bytes):
    ts_type = pkg_bytes[9]
    if ts_type != 3:
        return None
    year = pkg_bytes[11]
    month = pkg_bytes[12]
    day = pkg_bytes[13]
    hour = pkg_bytes[14]
    us_within_hour = struct.unpack("<I", pkg_bytes[15:19])[0]
    full_year = 2000 + year if year < 100 else year
    dt = datetime(full_year, month, day, hour, 0, 0, tzinfo=timezone.utc)
    return dt.timestamp() + us_within_hour / 1e6


def inspect(path, max_samples):
    path = Path(path)
    samples = []
    with open(path, "rb") as f:
        f.seek(24)
        frame_duration = struct.unpack("<I", f.read(4))[0]
        device_count = struct.unpack("<B", f.read(1))[0]
        f.seek(device_count * 59, 1)
        file_size = path.stat().st_size
        current_pos = f.tell()
        while current_pos < file_size and len(samples) < max_samples:
            f.seek(current_pos)
            hdr = f.read(24)
            if len(hdr) < 24:
                break
            next_offset = struct.unpack("<Q", hdr[8:16])[0]
            if next_offset <= current_pos or next_offset > file_size:
                break
            bytes_remaining = next_offset - (current_pos + 24)
            while bytes_remaining >= PACKAGE_HEADER_SIZE and len(samples) < max_samples:
                pkg = f.read(PACKAGE_HEADER_SIZE)
                if len(pkg) < PACKAGE_HEADER_SIZE:
                    break
                data_type = pkg[10]
                bytes_remaining -= PACKAGE_HEADER_SIZE
                if data_type == 6:
                    payload = f.read(24)
                    bytes_remaining -= 24
                    t = timestamp_unix(pkg)
                    samples.append((t, *struct.unpack("<ffffff", payload)))
                elif data_type in {0, 1, 2, 3, 4, 5, 7, 8}:
                    sizes = {
                        0: 100 * 13, 1: 100 * 9, 2: 96 * 14, 3: 96 * 10,
                        4: 48 * 28, 5: 48 * 20, 7: 32 * 42, 8: 32 * 30,
                    }
                    size = sizes[data_type]
                    f.seek(size, 1)
                    bytes_remaining -= size
                else:
                    break
            current_pos = next_offset
    print(f"frame_duration_ms={frame_duration}")
    print("t_unix,gx,gy,gz,ax,ay,az")
    for row in samples:
        print(",".join("" if v is None else f"{v:.9g}" for v in row))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lvx")
    parser.add_argument("--max-samples", type=int, default=20)
    args = parser.parse_args()
    inspect(args.lvx, args.max_samples)


if __name__ == "__main__":
    main()
