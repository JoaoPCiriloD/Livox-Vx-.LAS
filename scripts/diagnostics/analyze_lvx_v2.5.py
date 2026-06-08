#!/usr/bin/env python3
"""
LVX File Analyzer v2.5 - Based on official Livox LVX Specification v1.1.0.0

v2.5: Corrected expected MB/min ranges:
      - Single: 180-220 (was 25-40 - severely underestimated)
      - Dual:   700-850 (was 55-75 - severely underestimated)
      - Triple: 1500-1900 (was 80-110 - severely underestimated)
      Previous values seemed to come from Mid-40 reference, not Avia.
      Also added "utilization vs nominal" metric, more useful for bench tests.

v2.4: GPS UTC timestamp parsing fixed (Year/Month/Day/Hour + us-in-hour layout).
v2.3: timestamp parsing attempt (sec+ns) - INCORRECT.
v2.2: timestamp_type values corrected.
v2.1: Frame Header is 24 bytes per spec.
v2.0: Initial spec-based implementation.
"""
import sys
import struct
import os
import datetime

# Package payload sizes by data_type (per LVX v1.1.0.0 spec)
# Each package contains: 19-byte package header + N points of P bytes each
PACKAGE_HEADER_SIZE = 19  # device_idx(1) + version(1) + slot(1) + lidar_id(1) + reserved(1)
                          # + status(4) + ts_type(1) + data_type(1) + timestamp(8) = 19 bytes

POINT_SIZES_AND_COUNTS = {
    # data_type: (points_per_package, bytes_per_point, description)
    0: (100, 13, "Cartesian single return (MID only)"),
    1: (100, 9,  "Spherical single return (MID only)"),
    2: (96,  14, "Cartesian single return - Avia/Horizon"),
    3: (96,  10, "Spherical single return - Avia/Horizon"),
    4: (48,  28, "Cartesian DUAL return"),
    5: (48,  20, "Spherical DUAL return"),
    6: (1,   24, "IMU data (6 floats: gyro_xyz + acc_xyz)"),
    # Triple return (post v1.1.0.0):
    7: (32,  42, "Cartesian TRIPLE return"),
    8: (32,  30, "Spherical TRIPLE return"),
}

TIMESTAMP_TYPE_MAP = {
    0: "No sync (ns since sensor boot)",
    1: "PTP 1588 sync",
    2: "Reserved (NOT GPS - common confusion)",
    3: "GPS sync (PPS + UTC anchored) <-- OBJETIVO",
    4: "PPS only (no UTC)",
    5: "Unknown sync mode",
}

DEVICE_TYPE_MAP = {
    0: "LiDAR Hub",
    1: "Mid-40/Mid-100",
    2: "Tele-15",
    3: "Horizon",
    6: "Mid-70",
    7: "Avia",
    9: "HAP",
    10: "Mid-360",
}


def fmt_bytes(n):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} TB"


def analyze_lvx(filepath):
    if not os.path.exists(filepath):
        print(f"ERRO: arquivo nao encontrado: {filepath}")
        return

    filesize = os.path.getsize(filepath)
    print("=" * 70)
    print(f"LVX FILE ANALYZER v2 - Livox Spec v1.1.0.0")
    print("=" * 70)
    print(f"Arquivo:    {filepath}")
    print(f"Tamanho:    {filesize:,} bytes ({fmt_bytes(filesize)})")
    print()

    with open(filepath, 'rb') as f:
        # ---------------- PUBLIC HEADER BLOCK (24 bytes) ----------------
        signature_raw = f.read(16)
        signature = signature_raw[:10].decode('ascii', errors='replace')
        version = f.read(4)
        magic_bytes = f.read(4)
        magic_code = struct.unpack('<I', magic_bytes)[0]

        print("[PUBLIC HEADER]")
        print(f"  File signature:  '{signature}' (esperado: 'livox_tech')")
        print(f"  Version:         {version[0]}.{version[1]}.{version[2]}.{version[3]}")
        print(f"  Magic code:      0x{magic_code:08X} (esperado: 0xAC0EA767)")

        if signature != "livox_tech":
            print(f"  [AVISO] Assinatura nao bate com 'livox_tech'")
        if magic_code != 0xAC0EA767:
            print(f"  [AVISO] Magic code nao bate com 0xAC0EA767")
        print()

        # ---------------- PRIVATE HEADER BLOCK (5 bytes) ----------------
        frame_duration = struct.unpack('<I', f.read(4))[0]
        device_count = struct.unpack('<B', f.read(1))[0]

        print("[PRIVATE HEADER]")
        print(f"  Frame duration:  {frame_duration} ms (deve ser 50 em v1.1.0.0)")
        print(f"  Device count:    {device_count}")
        print()

        # ---------------- DEVICE INFO BLOCK (59 bytes per device) ----------------
        print("[DEVICE INFO]")
        devices = []
        for i in range(device_count):
            lidar_sn = f.read(16).rstrip(b'\x00').decode('ascii', errors='replace')
            hub_sn = f.read(16).rstrip(b'\x00').decode('ascii', errors='replace')
            device_idx = struct.unpack('<B', f.read(1))[0]
            device_type = struct.unpack('<B', f.read(1))[0]
            extrinsic_enable = struct.unpack('<B', f.read(1))[0]
            roll, pitch, yaw, x, y, z = struct.unpack('<6f', f.read(24))

            device_name = DEVICE_TYPE_MAP.get(device_type, f"Unknown ({device_type})")
            devices.append({
                'index': device_idx,
                'sn': lidar_sn,
                'type': device_type,
                'type_name': device_name
            })

            print(f"  Device #{device_idx}:")
            print(f"    LiDAR SN:        {lidar_sn}")
            print(f"    Hub SN:          {hub_sn if hub_sn else '(direto, sem hub)'}")
            print(f"    Type code:       {device_type} -> {device_name}")
            print(f"    Extrinsic:       {'enabled' if extrinsic_enable else 'disabled'}")
            print(f"    Roll/Pitch/Yaw:  {roll:.3f} / {pitch:.3f} / {yaw:.3f}")
            print(f"    X/Y/Z (m):       {x:.3f} / {y:.3f} / {z:.3f}")
        print()

        # ---------------- POINT CLOUD DATA BLOCK ----------------
        # Walking frames using next_offset (robust!)
        data_block_start = f.tell()
        print(f"[POINT DATA BLOCK]")
        print(f"  Inicio em offset: {data_block_start} bytes")
        print(f"  Tamanho do bloco: {fmt_bytes(filesize - data_block_start)}")
        print()

        # Stats
        frame_count = 0
        total_lidar_points = 0
        total_imu_packages = 0
        first_timestamp = None
        last_timestamp = None
        first_valid_timestamp = None
        last_valid_timestamp = None
        timestamp_types = {}
        data_types = {}
        package_count = 0
        bad_data_types = 0
        bad_timestamp_types = 0

        # For tracking timestamp progression
        timestamps_by_type = {}

        # Iterate frames using next_offset for robustness
        current_pos = data_block_start
        problems = []

        while current_pos < filesize:
            f.seek(current_pos)

            # Read frame header: 24 bytes per LVX v1.1.0.0 spec
            try:
                fhdr = f.read(24)
                if len(fhdr) < 24:
                    break
                current_offset = struct.unpack('<Q', fhdr[0:8])[0]
                next_offset    = struct.unpack('<Q', fhdr[8:16])[0]
                frame_index    = struct.unpack('<Q', fhdr[16:24])[0]
            except Exception as e:
                problems.append(f"Falha ao ler frame header em offset {current_pos}: {e}")
                break

            if current_offset != current_pos:
                problems.append(f"Frame {frame_index}: current_offset ({current_offset}) "
                                f"nao bate com posicao real ({current_pos})")

            if next_offset == 0 or next_offset <= current_pos:
                # End of file or invalid
                if next_offset == 0:
                    pass  # normal EOF marker
                else:
                    problems.append(f"Frame {frame_index}: next_offset invalido ({next_offset})")
                break

            if next_offset > filesize:
                problems.append(f"Frame {frame_index}: next_offset ({next_offset}) > filesize")
                break

            # Read all packages in this frame
            pkg_start = current_pos + 24
            pkg_end = next_offset

            f.seek(pkg_start)
            bytes_remaining = pkg_end - pkg_start

            while bytes_remaining >= PACKAGE_HEADER_SIZE:
                pkg_bytes = f.read(PACKAGE_HEADER_SIZE)
                if len(pkg_bytes) < PACKAGE_HEADER_SIZE:
                    break

                device_idx_p = pkg_bytes[0]
                version_p = pkg_bytes[1]
                slot_id = pkg_bytes[2]
                lidar_id = pkg_bytes[3]
                # pkg_bytes[4] = reserved
                status_code = struct.unpack('<I', pkg_bytes[5:9])[0]
                ts_type = pkg_bytes[9]
                data_type = pkg_bytes[10]
                # Timestamp parsing depends on sync mode (per official Livox SDK Protocol spec):
                # - Type 3 (GPS UTC): byte 0=year, byte 1=month, byte 2=day, byte 3=hour,
                #                     bytes 4-7=microseconds within the hour
                # - Other types: uint64 nanoseconds
                if ts_type == 3:
                    year = pkg_bytes[11]
                    month = pkg_bytes[12]
                    day = pkg_bytes[13]
                    hour = pkg_bytes[14]
                    us_within_hour = struct.unpack('<I', pkg_bytes[15:19])[0]
                    # Convert to ns since epoch for consistency with other types
                    try:
                        # year is 2-digit (00 = 2000), per common Livox firmware behavior
                        full_year = 2000 + year if year < 100 else year
                        dt = datetime.datetime(full_year, month, day, hour, 0, 0, tzinfo=datetime.timezone.utc)
                        epoch_seconds = dt.timestamp()
                        timestamp = int(epoch_seconds * 1_000_000_000 + us_within_hour * 1_000)
                    except (ValueError, OSError):
                        timestamp = 0
                else:
                    timestamp = struct.unpack('<Q', pkg_bytes[11:19])[0]

                bytes_remaining -= PACKAGE_HEADER_SIZE

                # Tally counters
                timestamp_types[ts_type] = timestamp_types.get(ts_type, 0) + 1
                data_types[data_type] = data_types.get(data_type, 0) + 1
                if ts_type not in TIMESTAMP_TYPE_MAP:
                    bad_timestamp_types += 1
                if data_type not in POINT_SIZES_AND_COUNTS:
                    bad_data_types += 1

                # Track timestamps by type
                if ts_type not in timestamps_by_type:
                    timestamps_by_type[ts_type] = {'first': timestamp, 'last': timestamp, 'count': 1}
                else:
                    timestamps_by_type[ts_type]['last'] = timestamp
                    timestamps_by_type[ts_type]['count'] += 1

                if first_timestamp is None:
                    first_timestamp = timestamp
                last_timestamp = timestamp

                # Determine payload size and read past it
                if data_type in POINT_SIZES_AND_COUNTS:
                    pts_per_pkg, bytes_per_pt, _ = POINT_SIZES_AND_COUNTS[data_type]
                    payload_size = pts_per_pkg * bytes_per_pt

                    if data_type == 6:
                        total_imu_packages += 1
                    else:
                        total_lidar_points += pts_per_pkg

                    if bytes_remaining < payload_size:
                        # Truncated package - skip to end of frame
                        problems.append(f"Frame {frame_index}: package truncado "
                                        f"(data_type={data_type}, esperado {payload_size}, "
                                        f"restante {bytes_remaining})")
                        break

                    f.read(payload_size)
                    bytes_remaining -= payload_size
                    package_count += 1
                else:
                    # Unknown data type - we can't know payload size
                    # Skip to next frame
                    problems.append(f"Frame {frame_index}: data_type desconhecido = {data_type}, "
                                    f"abortando frame")
                    break

            frame_count += 1
            current_pos = next_offset

        # ---------------- RESUMO ----------------
        print("[RESUMO]")
        print(f"  Frames processados:     {frame_count:,}")
        print(f"  Packages totais:        {package_count:,}")
        print(f"  Pontos LiDAR:           {total_lidar_points:,}")
        print(f"  Packages de IMU:        {total_imu_packages:,}")
        if frame_count > 0:
            duration_ms = frame_count * frame_duration
            print(f"  Duracao (frames*50ms):  {duration_ms/1000:.2f} s ({duration_ms/60000:.2f} min)")
            if duration_ms > 0:
                mb_per_min = (filesize / 1024 / 1024) / (duration_ms / 60000)
                print(f"  Taxa real:              {mb_per_min:.1f} MB/min")
                pts_per_sec = total_lidar_points / (duration_ms / 1000)
                print(f"  Pontos/segundo:         {pts_per_sec:,.0f}")
                imu_per_sec = total_imu_packages / (duration_ms / 1000)
                print(f"  IMU samples/segundo:    {imu_per_sec:.1f} (esperado: 200)")
        print()

        # ---------------- TIMESTAMP TYPES ----------------
        print("[TIMESTAMP TYPES]  (>>> CRITICO para GPS sync <<<)")
        total_pkg = sum(timestamp_types.values())
        # Only show types that are documented or have >0.1% representation
        for ts_type, count in sorted(timestamp_types.items()):
            pct = 100.0 * count / total_pkg if total_pkg > 0 else 0
            label = TIMESTAMP_TYPE_MAP.get(ts_type, f"DESCONHECIDO ({ts_type}) - possivel corrupcao")
            if ts_type in TIMESTAMP_TYPE_MAP or pct > 0.5:
                marker = "  " if pct < 1 else "**"
                print(f"  {marker} Type {ts_type:3d}: {count:8,} pkgs ({pct:5.2f}%) -> {label}")

        if bad_timestamp_types > 0:
            print(f"  [INFO] {bad_timestamp_types} packages com timestamp_type fora da spec "
                  f"(parsing ruim ou arquivo corrompido)")
        print()

        # ---------------- DATA TYPES ----------------
        print("[DATA TYPES]  (indica modo de retorno)")
        for dt, count in sorted(data_types.items()):
            pct = 100.0 * count / total_pkg if total_pkg > 0 else 0
            if dt in POINT_SIZES_AND_COUNTS:
                pts_per_pkg, bytes_per_pt, desc = POINT_SIZES_AND_COUNTS[dt]
                marker = "**" if pct >= 1 else "  "
                print(f"  {marker} Type {dt}: {count:8,} pkgs ({pct:5.2f}%) -> {desc}")

        if bad_data_types > 0:
            print(f"  [INFO] {bad_data_types} packages com data_type desconhecido")
        print()

        # ---------------- TIMESTAMP VALUES ----------------
        print("[TIMESTAMPS por tipo]")
        for ts_type, data in sorted(timestamps_by_type.items()):
            if ts_type not in TIMESTAMP_TYPE_MAP:
                continue
            label = TIMESTAMP_TYPE_MAP[ts_type]
            print(f"  Type {ts_type} ({label}):")
            print(f"    Primeiro: {data['first']:,} ns")
            print(f"    Ultimo:   {data['last']:,} ns")
            delta_ns = data['last'] - data['first']
            print(f"    Delta:    {delta_ns:,} ns ({delta_ns/1e9:.3f} s)")

            # Interpret based on type
            if ts_type == 3 or data['first'] > 1e18:
                # GPS sync: ns since epoch (1970-01-01)
                try:
                    dt_first = datetime.datetime.utcfromtimestamp(data['first'] / 1e9)
                    dt_last = datetime.datetime.utcfromtimestamp(data['last'] / 1e9)
                    print(f"    UTC:      {dt_first} -> {dt_last}")
                except (ValueError, OSError):
                    print(f"    [erro convertendo para UTC]")
            elif ts_type == 0:
                # No sync: ns since sensor boot
                print(f"    Interpretacao: {data['first']/1e9:.2f}s a {data['last']/1e9:.2f}s "
                      f"desde boot do sensor")
        print()

        # ---------------- PROBLEMAS ENCONTRADOS ----------------
        if problems:
            print(f"[PROBLEMAS] ({len(problems)} encontrados, mostrando primeiros 10)")
            for prob in problems[:10]:
                print(f"  - {prob}")
            print()

        # ---------------- DIAGNOSTICO FINAL ----------------
        print("=" * 70)
        print("DIAGNOSTICO")
        print("=" * 70)

        # GPS sync analysis (CORRECTED: type 3 is GPS, not 2)
        gps_pkgs = timestamp_types.get(3, 0)
        no_sync_pkgs = timestamp_types.get(0, 0)
        pps_only_pkgs = timestamp_types.get(4, 0)
        ptp_pkgs = timestamp_types.get(1, 0)
        reserved_pkgs = timestamp_types.get(2, 0)

        gps_pct = 100.0 * gps_pkgs / total_pkg if total_pkg > 0 else 0
        nosync_pct = 100.0 * no_sync_pkgs / total_pkg if total_pkg > 0 else 0

        print()
        print("GPS SYNC (timestamp_type = 3):")
        if gps_pct > 95:
            print(f"  [OK] GPS sync OK em {gps_pct:.1f}% dos pacotes")
        elif gps_pct > 50:
            print(f"  [PARCIAL] GPS sync em {gps_pct:.1f}% dos pacotes (esperado ~100%)")
            print(f"            Possivel: sync entrou no meio da gravacao")
        elif no_sync_pkgs > 0 and nosync_pct > 50:
            print(f"  [FALHOU] {nosync_pct:.1f}% dos pacotes SEM SYNC (ns desde boot do sensor)")
            print(f"            lidar_utc_sync NAO estava rodando durante gravacao")
        elif pps_only_pkgs > 0:
            print(f"  [PARCIAL] PPS-only sem UTC ancorado")
            print(f"            PPS chegou no Avia mas GPRMC nao foi injetado via SDK")
        else:
            print(f"  [INDETERMINADO] Distribuicao incomum de timestamp types")

        print()
        print("MODO DE RETORNO:")
        single_pkgs = data_types.get(2, 0) + data_types.get(3, 0) + data_types.get(0, 0) + data_types.get(1, 0)
        dual_pkgs = data_types.get(4, 0) + data_types.get(5, 0)
        triple_pkgs = data_types.get(7, 0) + data_types.get(8, 0)
        imu_pkgs = data_types.get(6, 0)
        total_data_pkgs = single_pkgs + dual_pkgs + triple_pkgs

        if total_data_pkgs > 0:
            single_pct = 100.0 * single_pkgs / total_data_pkgs
            dual_pct = 100.0 * dual_pkgs / total_data_pkgs
            triple_pct = 100.0 * triple_pkgs / total_data_pkgs

            print(f"  Single Return: {single_pkgs:7,} pkgs ({single_pct:5.1f}%)")
            print(f"  Dual Return:   {dual_pkgs:7,} pkgs ({dual_pct:5.1f}%)")
            print(f"  Triple Return: {triple_pkgs:7,} pkgs ({triple_pct:5.1f}%)")

            if triple_pct > 80:
                print(f"  Modo dominante: TRIPLE RETURN")
            elif dual_pct > 80:
                print(f"  Modo dominante: DUAL RETURN")
            elif single_pct > 80:
                print(f"  Modo dominante: SINGLE RETURN")
            else:
                print(f"  [AVISO] Modos misturados - possivel mudanca durante gravacao "
                      f"ou config inconsistente")

        print()
        print("IMU:")
        if imu_pkgs > 0:
            imu_rate = imu_pkgs / (duration_ms / 1000) if duration_ms > 0 else 0
            print(f"  {imu_pkgs:,} pacotes IMU ({imu_rate:.1f}/s)")
            if 180 <= imu_rate <= 220:
                print(f"  [OK] Taxa proxima do esperado (200 Hz)")
            elif imu_rate < 50:
                print(f"  [AVISO] Taxa muito baixa - IMU pode estar desabilitado ou perdendo dados")
        else:
            print(f"  [AVISO] Nenhum dado de IMU detectado")

        print()
        print("VOLUME DO ARQUIVO:")
        if duration_ms > 0 and frame_count > 0:
            mb_per_min_actual = (filesize / 1024 / 1024) / (duration_ms / 60000)
            # Expected rates based on dominant return mode (CORRECTED v2.4)
            # Based on Avia spec: nominal point rates * package overhead
            if total_data_pkgs > 0:
                if triple_pct > 80:
                    # 720k pts/s, 32 pts/pkg, 42 bytes/pt + 19 hdr = 22500 pkgs/s, 1363 bytes/pkg
                    expected_min, expected_max = 1500, 1900
                    mode = "Triple Return (full rate)"
                elif dual_pct > 80:
                    # 480k pts/s, 48 pts/pkg, 28 bytes/pt + 19 hdr = 10000 pkgs/s, 1363 bytes/pkg
                    expected_min, expected_max = 700, 850
                    mode = "Dual Return (full rate)"
                elif single_pct > 80:
                    # 240k pts/s, 96 pts/pkg, 14 bytes/pt + 19 hdr = 2500 pkgs/s, 1363 bytes/pkg
                    expected_min, expected_max = 180, 220
                    mode = "Single Return (full rate)"
                else:
                    expected_min, expected_max = 180, 1900
                    mode = "modo misto"

                print(f"  Taxa real:                  {mb_per_min_actual:.1f} MB/min")
                print(f"  Esperado (rate nominal):    {expected_min}-{expected_max} MB/min para {mode}")
                print(f"  Pontos/s real:              {pts_per_sec:,.0f}")
                ratio = mb_per_min_actual / ((expected_min + expected_max) / 2)
                print(f"  Utilizacao da capacidade:   {ratio*100:.0f}%")
                if ratio < 0.3:
                    print(f"  [INFO] Bench test sem alvos suficientes - normal ter taxa reduzida")
                elif ratio > 1.2:
                    print(f"  [ANOMALIA] Volume acima do esperado para o modo")
                else:
                    print(f"  [OK] Volume coerente com modo de retorno em condicao real")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 analyze_lvx_v2.py <caminho_do_arquivo.lvx>")
        print()
        print("Analyzer baseado na spec oficial Livox LVX v1.1.0.0")
        sys.exit(1)
    analyze_lvx(sys.argv[1])
