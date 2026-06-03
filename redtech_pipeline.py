#!/usr/bin/env python3
"""
redtech_pipeline.py v2.0
========================

Pipeline unificado RedTech: roda toda a validação + conversão + georef
em um único comando, processando pastas de sessão.

Uso:
    # Processa UMA pasta
    python3 redtech_pipeline.py "~/Downloads/Teste 1/voo_20260527_142555"

    # Processa TODAS as pastas filhas (batch)
    python3 redtech_pipeline.py "~/Downloads/Teste 1" --batch

Cada pasta de sessao deve conter:
    - 1 arquivo .lvx
    - 1 arquivo .ubx
    - 1 arquivo .log (str2str)

Output organizado em ~/RedTech/sessoes/<nome_pasta>/:
    input/
    output/
    relatorio.md
    metrics.json

RedTech Security
"""

import sys
import os
import shutil
import argparse
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    import numpy as np
    import laspy
    from pyubx2 import UBXReader
except ImportError as e:
    print(f"ERRO: biblioteca faltando — {e}")
    print("Instalar com: pip install laspy numpy pyubx2 pyproj")
    sys.exit(1)


# ============================================================
# CORES
# ============================================================

class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


OK = f"{C.GREEN}OK{C.END}"
WARN = f"{C.YELLOW}WARN{C.END}"
FAIL = f"{C.RED}FAIL{C.END}"


def header(text, char='='):
    print(f"\n{C.BOLD}{char * 70}{C.END}")
    print(f"{C.BOLD}{text}{C.END}")
    print(f"{C.BOLD}{char * 70}{C.END}")


def step(text):
    print(f"\n{C.BLUE}{C.BOLD}>> {text}{C.END}")


# ============================================================
# AUTO-DETECT DOS ARQUIVOS DENTRO DA PASTA
# ============================================================

def find_session_files(session_folder):
    folder = Path(session_folder)
    if not folder.is_dir():
        return None, None, None, "Pasta nao existe"

    lvx_files = sorted(folder.glob("*.lvx"),
                       key=lambda p: p.stat().st_size, reverse=True)
    ubx_files = sorted(folder.glob("*.ubx"),
                       key=lambda p: p.stat().st_size, reverse=True)
    log_files = (sorted(folder.glob("str2str*.log")) +
                 sorted(folder.glob("*str2str*.log")) +
                 sorted(folder.glob("str2str*.txt")))

    if not lvx_files:
        return None, None, None, "Nenhum .lvx encontrado"
    if not ubx_files:
        return None, None, None, "Nenhum .ubx encontrado"
    if not log_files:
        log_files = [None]

    if len(lvx_files) > 1:
        print(f"  {C.YELLOW}AVISO: {len(lvx_files)} arquivos .lvx — usando o maior: "
              f"{lvx_files[0].name}{C.END}")
    if len(ubx_files) > 1:
        print(f"  {C.YELLOW}AVISO: {len(ubx_files)} arquivos .ubx — usando o maior: "
              f"{ubx_files[0].name}{C.END}")

    return lvx_files[0], ubx_files[0], log_files[0], None


# ============================================================
# CONFIG
# ============================================================

class Config:
    def __init__(self, args, session_folder):
        self.session_folder = Path(session_folder)
        self.session_id = self.session_folder.name

        self.sessoes_dir = Path(args.output).expanduser()
        self.utm_zone = args.utm_zone
        self.hemisphere = args.hemisphere
        self.skip_cloudcompare = args.skip_cloudcompare
        self.skip_geo = args.skip_geo
        self.keep_local = args.keep_local
        self.scripts_dir = Path(args.scripts).expanduser()

        self.work_dir = self.sessoes_dir / self.session_id
        self.input_dir = self.work_dir / "input"
        self.output_dir = self.work_dir / "output"
        self.report_path = self.work_dir / "relatorio.md"
        self.metrics_path = self.work_dir / "metrics.json"

        # Conversor: ordem de preferencia robusta.
        # 1) nome canonico (lvx_to_las_redtech.py = sempre a versao boa/chunked)
        # 2) v3 explicito (chunked)
        # 3) v2 (legado — tem bug de dual return; ultimo recurso)
        canonical = self.scripts_dir / "lvx_to_las_redtech.py"
        v3 = self.scripts_dir / "lvx_to_las_redtech_v3.py"
        v2 = self.scripts_dir / "lvx_to_las_redtech_v2.py"
        if canonical.exists():
            self.convert_script = canonical
        elif v3.exists():
            self.convert_script = v3
        else:
            self.convert_script = v2
        self.georef_script = self.scripts_dir / "las_geo_redtech.py"
        self.lio_georef_script = self.scripts_dir / "las_lio_geo_redtech.py"
        self.geo_las_path = None
        self.lio_geo_las_path = None


# ============================================================
# RESULTS
# ============================================================

class Results:
    def __init__(self):
        self.session_id = None
        self.criteria = []
        self.metrics = {}
        self.errors = []
        self.duration_seconds = None

    def add(self, name, status, detail=""):
        self.criteria.append((name, status, detail))


# ============================================================
# ETAPA 1 — LOCALIZAR
# ============================================================

def step_1_locate_and_copy(cfg, results):
    step("Etapa 1/7 — Localizar arquivos da sessao")

    lvx, ubx, log, err = find_session_files(cfg.session_folder)
    if err:
        print(f"  [{FAIL}] {err}")
        results.errors.append(err)
        results.add("Arquivos da sessao", "fail", err)
        return None

    print(f"  [{OK}] LVX: {lvx.name} ({lvx.stat().st_size / 1e6:.1f} MB)")
    print(f"  [{OK}] UBX: {ubx.name} ({ubx.stat().st_size / 1e6:.1f} MB)")
    if log:
        print(f"  [{OK}] LOG: {log.name} ({log.stat().st_size} B)")
    else:
        print(f"  [{WARN}] str2str.log nao encontrado (nao fatal)")

    cfg.input_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    targets = {}
    for src in [lvx, ubx, log]:
        if src is None:
            continue
        dst = cfg.input_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        if src.suffix == '.lvx':
            targets['lvx'] = dst
        elif src.suffix == '.ubx':
            targets['ubx'] = dst
        else:
            targets['log'] = dst

    results.add("Arquivos da sessao", "pass", cfg.session_folder.name)

    return targets


# ============================================================
# ETAPA 2 — STR2STR.LOG
# ============================================================

def step_2_analyze_log(cfg, results, files):
    step("Etapa 2/7 — Analisar str2str.log")

    log_path = files.get('log')
    if log_path is None:
        print(f"  [{WARN}] Sem log")
        results.add("str2str rodou limpo", "warn", "Sem log")
        return True

    content = log_path.read_text(errors='replace')
    lines = content.strip().split('\n')

    has_start = any('stream server start' in l for l in lines)
    has_stop = any('stream server stop' in l for l in lines)
    has_error = any('error' in l.lower() for l in lines)
    status_lines = [l for l in lines if '[CC' in l]

    final_bytes = 0
    if status_lines:
        last = status_lines[-1]
        try:
            parts = last.split()
            for i, p in enumerate(parts):
                if p == 'B' and i > 0:
                    final_bytes = int(parts[i-1])
                    break
        except (ValueError, IndexError):
            pass

    print(f"  Stream start:     [{OK if has_start else FAIL}]")
    print(f"  Stream stop:      [{OK if has_stop else WARN}]")
    print(f"  Sem erros:        [{OK if not has_error else FAIL}]")
    print(f"  Status updates:   {len(status_lines)}")
    print(f"  Bytes acumulados: {final_bytes:,} B ({final_bytes/1024:.1f} KB)")

    results.metrics['str2str_bytes'] = final_bytes
    results.metrics['str2str_updates'] = len(status_lines)
    results.metrics['str2str_has_stop'] = has_stop

    if has_start and not has_error and final_bytes > 1000:
        results.add("str2str rodou limpo", "pass",
                    f"{len(status_lines)} updates, {final_bytes/1024:.1f} KB")
    elif has_error:
        results.add("str2str rodou limpo", "fail", "Erros no log")
    else:
        results.add("str2str rodou limpo", "warn",
                    "Sem stop limpo ou poucos bytes")
    return True


# ============================================================
# ETAPA 3 — UBX
# ============================================================

def step_3_analyze_ubx(cfg, results, files):
    step("Etapa 3/7 — Analisar gnss.ubx")

    ubx_path = files['ubx']
    data = ubx_path.read_bytes()
    total = data.count(b'\xb5\x62')
    nav_pvt_count = data.count(b'\xb5\x62\x01\x07')
    rxm_rawx_count = data.count(b'\xb5\x62\x02\x15')
    rxm_sfrbx_count = data.count(b'\xb5\x62\x02\x13')

    print(f"  Total UBX:    {total:,}")
    print(f"  NAV-PVT:      {nav_pvt_count:,}")
    print(f"  RXM-RAWX:     {rxm_rawx_count:,}")
    print(f"  RXM-SFRBX:    {rxm_sfrbx_count:,}")

    fix_count = 0
    sats_list = []
    pdop_list = []
    hacc_list = []
    lats = []
    lons = []
    timestamps = []

    with open(ubx_path, 'rb') as f:
        reader = UBXReader(f, protfilter=2)
        for raw, parsed in reader:
            if not parsed or not hasattr(parsed, 'identity'):
                continue
            if parsed.identity != 'NAV-PVT':
                continue
            try:
                if parsed.fixType >= 3:
                    ts = datetime(parsed.year, parsed.month, parsed.day,
                                  parsed.hour, parsed.min, parsed.second,
                                  tzinfo=timezone.utc)
                    timestamps.append(ts)
                    sats_list.append(parsed.numSV)
                    pdop_list.append(parsed.pDOP)
                    hacc_list.append(parsed.hAcc)
                    lats.append(parsed.lat)
                    lons.append(parsed.lon)
                    fix_count += 1
            except Exception:
                pass

    if not timestamps:
        print(f"  [{FAIL}] Nenhum NAV-PVT com fix 3D")
        results.add("UBX com fix 3D", "fail", "Nenhum fix")
        return False

    ubx_start = min(timestamps)
    ubx_end = max(timestamps)
    duration = (ubx_end - ubx_start).total_seconds()

    sats_avg = float(np.mean(sats_list))
    pdop_avg = float(np.mean(pdop_list))
    hacc_avg = float(np.mean(hacc_list))
    lat_avg = float(np.mean(lats))
    lon_avg = float(np.mean(lons))

    print(f"  Com fix 3D:       {fix_count}/{nav_pvt_count}")
    print(f"  Periodo UBX UTC:  {ubx_start} -> {ubx_end}")
    print(f"  Duracao:          {duration:.0f}s")
    print(f"  Satelites (med):  {sats_avg:.1f}")
    print(f"  pDOP (med):       {pdop_avg:.2f}")
    print(f"  hAcc (med):       {hacc_avg:.0f} mm")
    print(f"  Posicao centro:   lat={lat_avg:.6f}, lon={lon_avg:.6f}")

    results.metrics['ubx_nav_pvt'] = nav_pvt_count
    results.metrics['ubx_rxm_rawx'] = rxm_rawx_count
    results.metrics['ubx_rxm_sfrbx'] = rxm_sfrbx_count
    results.metrics['ubx_fix_count'] = fix_count
    results.metrics['ubx_start'] = ubx_start.isoformat()
    results.metrics['ubx_end'] = ubx_end.isoformat()
    results.metrics['ubx_duration'] = duration
    results.metrics['ubx_sats_avg'] = sats_avg
    results.metrics['ubx_pdop_avg'] = pdop_avg
    results.metrics['ubx_hacc_avg'] = hacc_avg
    results.metrics['ubx_lat'] = lat_avg
    results.metrics['ubx_lon'] = lon_avg

    fix_pct = 100.0 * fix_count / nav_pvt_count
    if fix_pct >= 95:
        results.add("Fix 3D >=95% NAV-PVT", "pass", f"{fix_pct:.1f}%")
    else:
        results.add("Fix 3D >=95% NAV-PVT", "fail", f"{fix_pct:.1f}%")

    if pdop_avg < 3:
        results.add("pDOP < 3 (excelente)", "pass", f"pDOP {pdop_avg:.2f}")
    elif pdop_avg < 5:
        results.add("pDOP < 5", "warn", f"pDOP {pdop_avg:.2f}")
    else:
        results.add("pDOP < 5", "fail", f"pDOP {pdop_avg:.2f}")

    if hacc_avg < 2000:
        results.add("hAcc < 2m", "pass", f"hAcc {hacc_avg:.0f}mm")
    elif hacc_avg < 5000:
        results.add("hAcc < 5m", "warn", f"hAcc {hacc_avg:.0f}mm")
    else:
        results.add("hAcc < 5m", "fail", f"hAcc {hacc_avg:.0f}mm")

    if rxm_rawx_count == 0:
        results.add("RXM-RAWX presente", "warn", "0 (sem PPK futuro)")
    elif rxm_rawx_count < 10:
        results.add("RXM-RAWX presente", "warn", f"{rxm_rawx_count} mensagens")
    else:
        results.add("RXM-RAWX presente", "pass", f"{rxm_rawx_count} mensagens")

    return True


# ============================================================
# ETAPA 4 — LVX
# ============================================================

def step_4_analyze_lvx(cfg, results, files):
    step("Etapa 4/7 — Analisar arquivo .lvx")

    import struct

    POINT_SIZES_AND_COUNTS = {
        0: (100, 13), 1: (100, 9), 2: (96, 14), 3: (96, 10),
        4: (48, 28), 5: (48, 20), 6: (1, 24), 7: (32, 42), 8: (32, 30),
    }
    PACKAGE_HEADER_SIZE = 19

    lvx_path = files['lvx']

    with open(lvx_path, 'rb') as f:
        f.seek(88)

        frames = 0
        pkgs_total = 0
        ts_type_3 = 0
        ts_type_other = 0
        imu_count = 0
        data_type_4 = 0
        data_type_2 = 0
        first_ts = None
        last_ts = None
        file_size = lvx_path.stat().st_size

        while f.tell() < file_size:
            fhdr = f.read(24)
            if len(fhdr) < 24:
                break
            try:
                current_offset = struct.unpack('<Q', fhdr[0:8])[0]
                next_offset = struct.unpack('<Q', fhdr[8:16])[0]
            except struct.error:
                break

            if next_offset <= current_offset or next_offset > file_size:
                break

            pkg_start = f.tell()
            bytes_remaining = next_offset - pkg_start

            while bytes_remaining >= PACKAGE_HEADER_SIZE:
                pkg_bytes = f.read(PACKAGE_HEADER_SIZE)
                if len(pkg_bytes) < PACKAGE_HEADER_SIZE:
                    break

                ts_type = pkg_bytes[9]
                data_type = pkg_bytes[10]

                if ts_type == 3:
                    ts_type_3 += 1
                    try:
                        year = pkg_bytes[11]
                        month = pkg_bytes[12]
                        day = pkg_bytes[13]
                        hour = pkg_bytes[14]
                        us_within_hour = struct.unpack('<I', pkg_bytes[15:19])[0]
                        full_year = 2000 + year if year < 100 else year
                        dt = datetime(full_year, month, day, hour, 0, 0,
                                      tzinfo=timezone.utc)
                        dt = dt + timedelta(microseconds=us_within_hour)
                        if first_ts is None or dt < first_ts:
                            first_ts = dt
                        if last_ts is None or dt > last_ts:
                            last_ts = dt
                    except (ValueError, OSError):
                        pass
                else:
                    ts_type_other += 1

                if data_type == 4:
                    data_type_4 += 1
                elif data_type == 2:
                    data_type_2 += 1
                elif data_type == 6:
                    imu_count += 1

                bytes_remaining -= PACKAGE_HEADER_SIZE

                if data_type in POINT_SIZES_AND_COUNTS:
                    pts, bpp = POINT_SIZES_AND_COUNTS[data_type]
                    payload_size = pts * bpp
                    if bytes_remaining < payload_size:
                        break
                    f.read(payload_size)
                    bytes_remaining -= payload_size
                    pkgs_total += 1
                else:
                    break

            frames += 1
            f.seek(next_offset)

    duration = (last_ts - first_ts).total_seconds() if first_ts and last_ts else 0
    sync_pct = 100.0 * ts_type_3 / (ts_type_3 + ts_type_other) if (ts_type_3 + ts_type_other) > 0 else 0
    imu_rate = imu_count / duration if duration > 0 else 0

    print(f"  Frames:           {frames}")
    print(f"  Packages:         {pkgs_total:,}")
    print(f"  ts_type=3:        {ts_type_3:,} ({sync_pct:.1f}%)")
    print(f"  ts_type outros:   {ts_type_other:,}")
    print(f"  Dual Return:      {data_type_4:,}")
    print(f"  Single Return:    {data_type_2:,}")
    print(f"  IMU samples:      {imu_count:,} ({imu_rate:.1f} Hz)")
    print(f"  Duracao:          {duration:.1f}s")
    print(f"  Periodo LVX UTC:  {first_ts} -> {last_ts}")

    results.metrics['lvx_size_mb'] = lvx_path.stat().st_size / 1e6
    results.metrics['lvx_frames'] = frames
    results.metrics['lvx_packages'] = pkgs_total
    results.metrics['lvx_ts_type_3_pct'] = sync_pct
    results.metrics['lvx_duration'] = duration
    results.metrics['lvx_imu_rate'] = imu_rate
    results.metrics['lvx_start'] = first_ts.isoformat() if first_ts else None
    results.metrics['lvx_end'] = last_ts.isoformat() if last_ts else None
    results.metrics['lvx_dual_return'] = data_type_4
    results.metrics['lvx_single_return'] = data_type_2

    if sync_pct >= 99:
        results.add("timestamp_type=3 100%", "pass", f"{sync_pct:.1f}%")
    elif sync_pct >= 95:
        results.add("timestamp_type=3 >=95%", "warn", f"{sync_pct:.1f}%")
    else:
        results.add("timestamp_type=3 >=95%", "fail", f"{sync_pct:.1f}%")

    if 195 <= imu_rate <= 210:
        results.add("IMU rate ~200Hz", "pass", f"{imu_rate:.1f}Hz")
    else:
        results.add("IMU rate ~200Hz", "warn", f"{imu_rate:.1f}Hz")

    return True


# ============================================================
# ETAPA 5 — COBERTURA
# ============================================================

def step_5_validate_overlap(cfg, results):
    step("Etapa 5/7 — Validar cobertura temporal UBX vs LVX")

    if not results.metrics.get('ubx_start') or not results.metrics.get('lvx_start'):
        print(f"  [{WARN}] Metricas incompletas")
        return True

    ubx_start = datetime.fromisoformat(results.metrics['ubx_start'])
    ubx_end = datetime.fromisoformat(results.metrics['ubx_end'])
    lvx_start = datetime.fromisoformat(results.metrics['lvx_start'])
    lvx_end = datetime.fromisoformat(results.metrics['lvx_end'])

    margin_start = (lvx_start - ubx_start).total_seconds()
    margin_end = (ubx_end - lvx_end).total_seconds()

    print(f"  UBX:           {ubx_start} -> {ubx_end}")
    print(f"  LVX:           {lvx_start} -> {lvx_end}")
    print(f"  Margem inicio: {margin_start:+.1f}s")
    print(f"  Margem fim:    {margin_end:+.1f}s")

    results.metrics['margin_start'] = margin_start
    results.metrics['margin_end'] = margin_end

    if margin_start >= 0 and margin_end >= 0:
        results.add("UBX cobre LVX", "pass",
                    f"margens +{margin_start:.1f}s/+{margin_end:.1f}s")
    elif margin_start >= -2 and margin_end >= -2:
        results.add("UBX cobre LVX", "warn",
                    f"margens {margin_start:+.1f}s/{margin_end:+.1f}s")
    else:
        results.add("UBX cobre LVX", "fail",
                    f"margens {margin_start:+.1f}s/{margin_end:+.1f}s")
    return True


# ============================================================
# ETAPA 6 — LIO
# ============================================================

def step_6_assess_lio_readiness(cfg, results):
    step("Etapa 6/7 — Avaliar reconstrucao de trajetoria LIO")

    m = results.metrics
    imu_rate = m.get('lvx_imu_rate', 0) or 0
    sync_pct = m.get('lvx_ts_type_3_pct', 0) or 0
    margin_start = m.get('margin_start')
    margin_end = m.get('margin_end')

    has_imu = imu_rate >= 150
    has_sync = sync_pct >= 95
    has_temporal_overlap = (
        margin_start is not None and margin_end is not None and
        margin_start >= -2 and margin_end >= -2
    )

    ready_inputs = has_imu and has_sync and has_temporal_overlap

    print(f"  IMU no LVX:          [{OK if has_imu else WARN}] {imu_rate:.1f} Hz")
    print(f"  Timestamp LiDAR:     [{OK if has_sync else WARN}] {sync_pct:.1f}% type=3")
    if margin_start is not None and margin_end is not None:
        print(f"  Cobertura temporal:  [{OK if has_temporal_overlap else WARN}] "
              f"{margin_start:+.1f}s/{margin_end:+.1f}s")
    else:
        print(f"  Cobertura temporal:  [{WARN}] nao calculada")

    print(f"  Pre-requisitos LIO:  [{OK if ready_inputs else WARN}] "
          f"{'prontos' if ready_inputs else 'incompletos'}")
    print("  Metodo interno:      integracao IMU + translacao GNSS")
    print("  Refinamento futuro:  LIO-SAM/FAST-LIO com scan matching")

    m['lio_required'] = True
    m['lio_applied'] = False
    m['lio_ready_inputs'] = ready_inputs
    m['lio_has_imu'] = has_imu
    m['lio_has_lidar_time_sync'] = has_sync
    m['lio_has_temporal_overlap'] = has_temporal_overlap
    m['lio_current_pipeline'] = (
        "conversao LVX->LAS + translacao GNSS interpolada em UTM"
    )
    m['lio_recommended_step'] = (
        "reconstrucao de trajetoria por odometria LiDAR-inercial antes da "
        "nuvem final de analise"
    )
    m['lio_recommended_frameworks'] = ["LIO-SAM", "FAST-LIO", "LI-RTO"]
    m['lio_processing_steps'] = [
        "sincronizacao temporal estrita entre LiDAR e IMU",
        "calibracao extrinseca LiDAR-IMU",
        "integracao inercial para previsao de pose em alta frequencia",
        "scan matching/ICP entre varreduras LiDAR",
        "correcao por EKF ou otimizacao em grafo de fatores",
    ]

    if ready_inputs:
        results.add("Pre-requisitos LIO", "pass",
                    "IMU, timestamps e cobertura temporal OK")
    else:
        results.add("Pre-requisitos LIO", "warn",
                    "Verificar IMU, timestamps ou cobertura temporal")

    return True


# ============================================================
# ETAPA 7 — PIPELINE
# ============================================================

def step_7_run_pipeline(cfg, results, files):
    step("Etapa 7/7 — Conversao e georeferenciamento")

    lvx_input = files['lvx']
    ubx_input = files['ubx']

    local_las = cfg.output_dir / f"{lvx_input.stem}_local.las"
    geo_las = cfg.output_dir / f"{lvx_input.stem}_geo.las"
    lio_geo_las = cfg.output_dir / f"{lvx_input.stem}_lio_geo.las"
    lio_traj_csv = cfg.output_dir / f"trajetoria_lio_{lvx_input.stem}.csv"

    if local_las.exists():
        print(f"  [INFO] {local_las.name} ja existe, pulando")
    else:
        print(f"  Rodando {cfg.convert_script.name}...")
        t0 = time.time()
        cmd = [sys.executable, str(cfg.convert_script),
               str(lvx_input), '-o', str(local_las), '--quiet']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - t0

        if proc.returncode != 0:
            print(f"  [{FAIL}] Conversao falhou em {elapsed:.1f}s")
            # Traceback COMPLETO no terminal (sem cortar) e salvo em log
            full_err = (proc.stderr or "") + "\n" + (proc.stdout or "")
            print(full_err)
            error_log = cfg.work_dir / "erro_conversao.txt"
            try:
                error_log.write_text(full_err)
                print(f"  [INFO] Traceback completo salvo em: {error_log}")
            except OSError:
                pass
            # Remover .las vazio/parcial para nao enganar o CloudCompare
            if local_las.exists():
                try:
                    local_las.unlink()
                    print(f"  [INFO] Removido .las parcial/vazio")
                except OSError:
                    pass
            results.add("Conversao .lvx -> .las", "fail",
                        "ver erro_conversao.txt na pasta da sessao")
            return False

        print(f"  [{OK}] Conversao OK em {elapsed:.1f}s")

    if not local_las.exists():
        results.add("Conversao .lvx -> .las", "fail", "Arquivo nao gerado")
        return False

    las = laspy.read(str(local_las))
    n_points_local = len(las.points)
    print(f"  Pontos no .las local: {n_points_local:,}")

    # Guarda: se gerou 0 pontos, e falha (nao adianta seguir pra georef)
    if n_points_local == 0:
        print(f"  [{FAIL}] .las gerado com ZERO pontos — algo falhou na conversao")
        results.add("Conversao gerou pontos", "fail", "0 pontos no .las")
        try:
            local_las.unlink()
        except OSError:
            pass
        return False

    results.metrics['las_local_points'] = n_points_local
    results.metrics['las_local_size_mb'] = local_las.stat().st_size / 1e6
    results.add("Conversao .lvx -> .las Format 3", "pass",
                f"{n_points_local:,} pontos")

    if cfg.skip_geo:
        print(f"  [INFO] Georef pulado")
        return True

    if geo_las.exists():
        print(f"  [INFO] {geo_las.name} ja existe, pulando")
    else:
        print(f"\n  Rodando las_geo_redtech.py...")
        t0 = time.time()
        cmd = [sys.executable, str(cfg.georef_script),
               str(local_las), str(ubx_input), '-o', str(geo_las),
               '--utm-zone', str(cfg.utm_zone),
               '--hemisphere', cfg.hemisphere,
               '--quiet']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - t0

        if proc.returncode != 0:
            print(f"  [{FAIL}] Georef falhou em {elapsed:.1f}s")
            print(proc.stderr[:500])
            results.add("Georef UTM", "fail", proc.stderr[:200])
            return False

        print(f"  [{OK}] Georef OK em {elapsed:.1f}s")

    cfg.geo_las_path = geo_las

    las_geo = laspy.read(str(geo_las))
    x_min, x_max = float(las_geo.x.min()), float(las_geo.x.max())
    y_min, y_max = float(las_geo.y.min()), float(las_geo.y.max())
    z_min, z_max = float(las_geo.z.min()), float(las_geo.z.max())

    try:
        import pyproj
        if cfg.hemisphere == 'south':
            utm = pyproj.CRS(f'EPSG:327{cfg.utm_zone:02d}')
        else:
            utm = pyproj.CRS(f'EPSG:326{cfg.utm_zone:02d}')
        wgs84 = pyproj.CRS('EPSG:4326')
        transformer = pyproj.Transformer.from_crs(utm, wgs84, always_xy=True)
        center_lon, center_lat = transformer.transform(
            (x_min + x_max) / 2, (y_min + y_max) / 2)
    except Exception:
        center_lat = None
        center_lon = None

    print(f"  UTM X:        {x_min:,.2f} a {x_max:,.2f}")
    print(f"  UTM Y:        {y_min:,.2f} a {y_max:,.2f}")
    print(f"  Z:            {z_min:.2f} a {z_max:.2f}")
    if center_lat is not None:
        print(f"  Centro:       lat={center_lat:.6f}, lon={center_lon:.6f}")
        print(f"  Google Maps:  https://www.google.com/maps?q={center_lat},{center_lon}")

    results.metrics['geo_x_min'] = x_min
    results.metrics['geo_x_max'] = x_max
    results.metrics['geo_y_min'] = y_min
    results.metrics['geo_y_max'] = y_max
    results.metrics['geo_z_min'] = z_min
    results.metrics['geo_z_max'] = z_max
    results.metrics['geo_center_lat'] = center_lat
    results.metrics['geo_center_lon'] = center_lon
    results.metrics['utm_zone'] = cfg.utm_zone
    results.metrics['hemisphere'] = cfg.hemisphere
    results.add("Georef UTM", "pass",
                f"Zone {cfg.utm_zone}{cfg.hemisphere.upper()[0]}")

    if cfg.lio_georef_script.exists():
        if lio_geo_las.exists():
            print(f"  [INFO] {lio_geo_las.name} ja existe, pulando LIO")
        else:
            print(f"\n  Rodando las_lio_geo_redtech.py...")
            t0 = time.time()
            cmd = [sys.executable, str(cfg.lio_georef_script),
                   str(local_las), str(ubx_input), str(lvx_input),
                   '-o', str(lio_geo_las),
                   '--trajectory-csv', str(lio_traj_csv),
                   '--utm-zone', str(cfg.utm_zone),
                   '--hemisphere', cfg.hemisphere,
                   '--quiet']
            proc = subprocess.run(cmd, capture_output=True, text=True)
            elapsed = time.time() - t0

            if proc.returncode != 0:
                print(f"  [{FAIL}] LIO georef falhou em {elapsed:.1f}s")
                full_err = (proc.stderr or "") + "\n" + (proc.stdout or "")
                print(full_err[:1000])
                error_log = cfg.work_dir / "erro_lio.txt"
                try:
                    error_log.write_text(full_err)
                    print(f"  [INFO] Log LIO salvo em: {error_log}")
                except OSError:
                    pass
                results.add("Georef LIO UTM", "fail", "ver erro_lio.txt")
            else:
                print(f"  [{OK}] LIO georef OK em {elapsed:.1f}s")

        if lio_geo_las.exists():
            cfg.lio_geo_las_path = lio_geo_las
            las_lio = laspy.read(str(lio_geo_las))
            results.metrics['lio_las_points'] = len(las_lio.points)
            results.metrics['lio_las_size_mb'] = lio_geo_las.stat().st_size / 1e6
            results.metrics['lio_output_las'] = str(lio_geo_las)
            results.metrics['lio_trajectory_csv'] = str(lio_traj_csv)
            results.metrics['lio_applied'] = True
            results.add("Georef LIO UTM", "pass",
                        f"{len(las_lio.points):,} pontos")
    else:
        results.add("Georef LIO UTM", "warn",
                    f"Script nao encontrado: {cfg.lio_georef_script}")

    # Limpeza do .las local (a menos que --keep-local seja passado)
    if not cfg.keep_local and local_las.exists():
        try:
            size_freed = local_las.stat().st_size / 1e6
            local_las.unlink()
            print(f"\n  [INFO] {local_las.name} removido ({size_freed:.1f} MB liberados)")
            print(f"         (use --keep-local para preservar o arquivo intermediario)")
            results.metrics['local_las_kept'] = False
        except Exception as e:
            print(f"  [WARN] Nao foi possivel remover {local_las.name}: {e}")
    else:
        results.metrics['local_las_kept'] = True

    return True


# ============================================================
# REPORT
# ============================================================

def write_report(cfg, results):
    import json

    metrics_full = {
        'session_id': cfg.session_id,
        'source_folder': str(cfg.session_folder),
        'duration_seconds': results.duration_seconds,
        'criteria': [(n, s, d) for n, s, d in results.criteria],
        'metrics': results.metrics,
        'errors': results.errors,
        'generated_at': datetime.now().isoformat(),
    }
    cfg.metrics_path.write_text(json.dumps(metrics_full, indent=2, default=str))

    m = results.metrics
    lines = []
    lines.append(f"# Relatorio — {cfg.session_id}")
    lines.append("")
    lines.append(f"**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Pasta de origem:** `{cfg.session_folder}`")
    lines.append(f"**Pipeline rodou em:** {results.duration_seconds:.1f}s")
    lines.append("")

    n_pass = sum(1 for _, s, _ in results.criteria if s == 'pass')
    n_warn = sum(1 for _, s, _ in results.criteria if s == 'warn')
    n_fail = sum(1 for _, s, _ in results.criteria if s == 'fail')
    total = len(results.criteria)

    lines.append("## Status Geral")
    lines.append("")
    lines.append(f"- Passou: **{n_pass}**/{total}")
    lines.append(f"- Aviso:  **{n_warn}**/{total}")
    lines.append(f"- Falhou: **{n_fail}**/{total}")
    lines.append("")
    lines.append(f"**Conclusao:** {'Pipeline validado.' if n_fail == 0 else 'Falhas detectadas.'}")
    lines.append("")

    lines.append("## Criterios")
    lines.append("")
    lines.append("| Criterio | Status | Detalhe |")
    lines.append("|----------|:---:|---------|")
    for name, status, detail in results.criteria:
        icon = {'pass': 'OK', 'warn': 'WARN', 'fail': 'FAIL'}[status]
        lines.append(f"| {name} | {icon} | {detail} |")
    lines.append("")

    lines.append("## Metricas")
    lines.append("")
    lines.append("### Periodo de Captura (UTC)")
    lines.append("")
    if m.get('lvx_start'):
        lines.append(f"- LVX:  `{m['lvx_start']}` -> `{m['lvx_end']}`")
    if m.get('ubx_start'):
        lines.append(f"- UBX:  `{m['ubx_start']}` -> `{m['ubx_end']}`")
    lines.append("")

    lines.append("### str2str.log")
    lines.append("")
    lines.append(f"- Bytes: {m.get('str2str_bytes', 0):,} B")
    lines.append(f"- Updates: {m.get('str2str_updates', 0)}")
    lines.append(f"- Stop limpo: {'Sim' if m.get('str2str_has_stop') else 'Nao'}")
    lines.append("")

    lines.append("### gnss.ubx")
    lines.append("")
    lines.append(f"- NAV-PVT total: {m.get('ubx_nav_pvt', 0):,}")
    lines.append(f"- Com fix 3D: {m.get('ubx_fix_count', 0):,}")
    lines.append(f"- RXM-RAWX: {m.get('ubx_rxm_rawx', 0):,}")
    lines.append(f"- RXM-SFRBX: {m.get('ubx_rxm_sfrbx', 0):,}")
    lines.append(f"- Duracao: {m.get('ubx_duration', 0):.1f}s")
    lines.append(f"- Satelites (media): {m.get('ubx_sats_avg', 0):.1f}")
    lines.append(f"- pDOP (media): {m.get('ubx_pdop_avg', 0):.2f}")
    lines.append(f"- hAcc (media): {m.get('ubx_hacc_avg', 0):.0f} mm")
    lines.append(f"- Posicao: lat={m.get('ubx_lat', 0):.6f}, lon={m.get('ubx_lon', 0):.6f}")
    lines.append("")

    lines.append("### lidar.lvx")
    lines.append("")
    lines.append(f"- Tamanho: {m.get('lvx_size_mb', 0):.1f} MB")
    lines.append(f"- Frames: {m.get('lvx_frames', 0):,}")
    lines.append(f"- Packages: {m.get('lvx_packages', 0):,}")
    lines.append(f"- timestamp_type=3: {m.get('lvx_ts_type_3_pct', 0):.1f}%")
    lines.append(f"- Duracao: {m.get('lvx_duration', 0):.1f}s")
    lines.append(f"- IMU rate: {m.get('lvx_imu_rate', 0):.1f} Hz")
    lines.append(f"- Dual Return: {m.get('lvx_dual_return', 0):,}")
    lines.append(f"- Single Return: {m.get('lvx_single_return', 0):,}")
    lines.append("")

    lines.append("### Cobertura temporal")
    lines.append("")
    lines.append(f"- Margem inicio: {m.get('margin_start', 0):+.1f}s")
    lines.append(f"- Margem fim: {m.get('margin_end', 0):+.1f}s")
    lines.append("")

    lines.append("### Reconstrucao de Trajetoria LiDAR-Inercial (LIO)")
    lines.append("")
    lines.append("- Status: etapa recomendada, ainda nao aplicada neste pipeline.")
    lines.append(f"- Pipeline atual: {m.get('lio_current_pipeline', 'georef GNSS')}.")
    lines.append(f"- Entradas prontas para LIO: "
                 f"{'Sim' if m.get('lio_ready_inputs') else 'Nao'}")
    lines.append(f"- IMU no LVX: {'Sim' if m.get('lio_has_imu') else 'Nao'} "
                 f"({m.get('lvx_imu_rate', 0):.1f} Hz)")
    lines.append(f"- Timestamp LiDAR sincronizado: "
                 f"{'Sim' if m.get('lio_has_lidar_time_sync') else 'Nao'} "
                 f"({m.get('lvx_ts_type_3_pct', 0):.1f}% type=3)")
    lines.append("- Observacao: para reduzir borramento por movimento em voo, "
                 "a nuvem final deve considerar odometria LiDAR-inercial. "
                 "A IMU fornece previsao de pose em alta frequencia e o "
                 "LiDAR corrige deriva por alinhamento geometrico entre "
                 "varreduras.")
    lines.append("- Etapas tecnicas: sincronizacao temporal LiDAR/IMU, "
                 "calibracao extrinseca, integracao inercial, scan "
                 "matching/ICP e correcao por EKF ou otimizacao em grafo.")
    frameworks = m.get('lio_recommended_frameworks') or [
        "LIO-SAM", "FAST-LIO", "LI-RTO"
    ]
    lines.append(f"- Frameworks recomendados: {', '.join(frameworks)}.")
    lines.append("")

    lines.append("### Saidas do pipeline")
    lines.append("")
    if 'las_local_points' in m:
        kept = m.get('local_las_kept', True)
        status = "(preservado)" if kept else "(removido apos georef)"
        lines.append(f"- .las local: {m['las_local_points']:,} pontos "
                     f"({m.get('las_local_size_mb', 0):.1f} MB) {status}")
    if 'geo_x_min' in m:
        lines.append(f"- UTM X: {m['geo_x_min']:,.2f} a {m['geo_x_max']:,.2f}")
        lines.append(f"- UTM Y: {m['geo_y_min']:,.2f} a {m['geo_y_max']:,.2f}")
        lines.append(f"- Z: {m['geo_z_min']:.2f} a {m['geo_z_max']:.2f}")
        if m.get('geo_center_lat') is not None:
            lines.append(f"- Centro: lat={m['geo_center_lat']:.6f}, "
                         f"lon={m['geo_center_lon']:.6f}")
            lines.append(f"- Google Maps: https://www.google.com/maps?q="
                         f"{m['geo_center_lat']},{m['geo_center_lon']}")
    if 'lio_las_points' in m:
        lines.append(f"- .las LIO georreferenciado: {m['lio_las_points']:,} pontos "
                     f"({m.get('lio_las_size_mb', 0):.1f} MB)")
        lines.append(f"- Arquivo LIO: `{m.get('lio_output_las')}`")
        lines.append(f"- Trajetoria LIO CSV: `{m.get('lio_trajectory_csv')}`")
    lines.append("")

    if results.errors:
        lines.append("## Erros")
        lines.append("")
        for err in results.errors:
            lines.append(f"- {err}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Relatorio gerado por redtech_pipeline.py v2.0*")

    cfg.report_path.write_text('\n'.join(lines))


def open_cloudcompare(cfg):
    if cfg.skip_cloudcompare:
        return
    if cfg.geo_las_path is None or not cfg.geo_las_path.exists():
        return

    if sys.platform == 'darwin':
        subprocess.Popen(['open', '-a', 'CloudCompare', str(cfg.geo_las_path)])
    elif sys.platform.startswith('linux'):
        subprocess.Popen(['cloudcompare', str(cfg.geo_las_path)])
    elif sys.platform == 'win32':
        # CloudCompare pode estar em locais diferentes no Windows.
        # Tenta varios caminhos conhecidos.
        candidates = [
            r'C:\Program Files\CloudCompare\CloudCompare.exe',
            r'C:\Program Files (x86)\CloudCompare\CloudCompare.exe',
        ]
        # Tambem tenta achar via PATH
        import shutil as _shutil
        found = _shutil.which('CloudCompare')
        if found:
            candidates.insert(0, found)

        for exe in candidates:
            if Path(exe).exists():
                subprocess.Popen([exe, str(cfg.geo_las_path)])
                return

        # Nao achou — avisa mas nao quebra
        print(f"  [INFO] CloudCompare nao encontrado automaticamente.")
        print(f"         Abra manualmente: {cfg.geo_las_path}")


def print_session_summary(cfg, results):
    n_pass = sum(1 for _, s, _ in results.criteria if s == 'pass')
    n_warn = sum(1 for _, s, _ in results.criteria if s == 'warn')
    n_fail = sum(1 for _, s, _ in results.criteria if s == 'fail')
    total = len(results.criteria)

    header(f"SUMARIO — {cfg.session_id}")
    print(f"  [{OK}]   Passou: {n_pass}/{total}")
    print(f"  [{WARN}] Aviso:  {n_warn}/{total}")
    print(f"  [{FAIL}] Falhou: {n_fail}/{total}")
    print(f"\n  Pipeline rodou em {results.duration_seconds:.1f}s")
    print(f"  Relatorio: {cfg.report_path}")

    m = results.metrics
    if m.get('geo_center_lat') is not None:
        print(f"\n  Google Maps: https://www.google.com/maps?q="
              f"{m['geo_center_lat']},{m['geo_center_lon']}")


def process_session(session_folder, args):
    cfg = Config(args, session_folder)
    results = Results()
    results.session_id = cfg.session_id

    t_start = time.time()

    header(f"PROCESSANDO SESSAO: {cfg.session_id}")
    print(f"Origem: {cfg.session_folder}")
    print(f"Output: {cfg.work_dir}")
    print(f"UTM:    Zone {cfg.utm_zone}{cfg.hemisphere.upper()[0]}")

    files = step_1_locate_and_copy(cfg, results)
    if not files:
        results.duration_seconds = time.time() - t_start
        write_report(cfg, results)
        return cfg, results

    step_2_analyze_log(cfg, results, files)
    if not step_3_analyze_ubx(cfg, results, files):
        results.duration_seconds = time.time() - t_start
        write_report(cfg, results)
        return cfg, results

    step_4_analyze_lvx(cfg, results, files)
    step_5_validate_overlap(cfg, results)
    step_6_assess_lio_readiness(cfg, results)
    step_7_run_pipeline(cfg, results, files)

    results.duration_seconds = time.time() - t_start
    write_report(cfg, results)
    print_session_summary(cfg, results)
    open_cloudcompare(cfg)

    return cfg, results


def find_session_folders(parent):
    parent = Path(parent)
    if not parent.is_dir():
        return []
    subfolders = []
    for child in sorted(parent.iterdir()):
        if child.is_dir() and any(child.glob("*.lvx")):
            subfolders.append(child)
    return subfolders


def main():
    parser = argparse.ArgumentParser(
        description='Pipeline RedTech: validacao + conversao + georef',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # UMA pasta
  python3 redtech_pipeline.py "~/Downloads/Teste 1/voo_20260527_142555"

  # TODAS as pastas filhas (batch)
  python3 redtech_pipeline.py "~/Downloads/Teste 1" --batch

  # Outras opcoes:
  --utm-zone 19         (Acre)
  --hemisphere north    (Roraima)
  --skip-cloudcompare
  --skip-geo
  --keep-local          (preserva o .las local intermediario)
"""
    )
    parser.add_argument('folder', type=str,
                        help='Pasta da sessao OU pasta-mae (use --batch)')
    parser.add_argument('--batch', action='store_true',
                        help='Processar todas subpastas filhas')
    parser.add_argument('--output', type=str, default='~/RedTech/sessoes',
                        help='Pasta raiz de sessoes processadas')
    parser.add_argument('--scripts', type=str, default='~/Downloads',
                        help='Pasta com os scripts auxiliares')
    parser.add_argument('--utm-zone', type=int, default=22)
    parser.add_argument('--hemisphere', type=str, default='south',
                        choices=['south', 'north'])
    parser.add_argument('--skip-cloudcompare', action='store_true')
    parser.add_argument('--skip-geo', action='store_true')
    parser.add_argument('--keep-local', action='store_true',
                        help='Preservar arquivo intermediario _local.las (default: apaga apos georef)')

    args = parser.parse_args()

    folder = Path(args.folder).expanduser()

    if not folder.exists():
        print(f"ERRO: pasta nao existe: {folder}")
        sys.exit(1)

    if args.batch:
        subfolders = find_session_folders(folder)
        if not subfolders:
            print(f"ERRO: nenhuma subpasta com .lvx em {folder}")
            sys.exit(1)

        header(f"MODO BATCH — {len(subfolders)} sessoes")
        for sf in subfolders:
            print(f"  - {sf.name}")

        all_results = []
        for sf in subfolders:
            args_session = argparse.Namespace(**vars(args))
            args_session.skip_cloudcompare = True  # nao abrir N janelas
            cfg, res = process_session(sf, args_session)
            all_results.append((cfg, res))

        header(f"SUMARIO BATCH — {len(all_results)} sessoes")
        for cfg, res in all_results:
            n_pass = sum(1 for _, s, _ in res.criteria if s == 'pass')
            n_warn = sum(1 for _, s, _ in res.criteria if s == 'warn')
            n_fail = sum(1 for _, s, _ in res.criteria if s == 'fail')
            total = len(res.criteria)
            status = OK if n_fail == 0 else FAIL
            print(f"  [{status}] {cfg.session_id} "
                  f"({n_pass}/{total} OK, {n_warn} warn, {n_fail} fail) "
                  f"em {res.duration_seconds:.1f}s")
        print()
        print(f"  Relatorios em: {Path(args.output).expanduser()}")
        print(f"  Para comparar: python3 redtech_compare.py --all")
    else:
        process_session(folder, args)


if __name__ == '__main__':
    main()
