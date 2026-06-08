#!/usr/bin/env python3
"""
lvx_to_las_ajr.py v3.1
==========================

Converte arquivos .lvx (Livox Avia) para .las Point Format 3 preservando
GPS time absoluto de cada ponto, mantendo coordenadas LOCAIS do sensor
(sem aplicar trajetoria GNSS).

v3.1 (29/05/2026): CORRECAO de bug que escapou no teste sintetico.
                   struct.unpack usava 'b' (signed int8, -128..127) para
                   reflectivity. Quando o Avia gerava valor > 127 (acontece
                   sempre em superficies refletivas), o numero virava
                   negativo e o np.array(..., dtype=np.uint16) estourava
                   com OverflowError. Trocado para 'B' (unsigned int8,
                   0..255) em todos os data_types (2, 4, 7).
                   Bug nao apareceu no teste sintetico porque os valores
                   gerados eram 50 e 80 — ambos abaixo de 127.

v3.0 (28/05/2026): CHUNKED WRITING — escreve o .las em blocos durante o
                   processamento em vez de acumular tudo na RAM. Resolve
                   risco de estouro de memoria em voos longos (5-20 min).
                   Antes: voo de 20 min (~340M pontos) podia exigir >16GB RAM.
                   Agora: uso de RAM constante (~poucos MB por bloco).

v2.0 (27/05/2026): Reescrito baseado na logica EXATA do analyze_lvx_v2.5.py
                   que sabemos parsear corretamente.

Diferenca em relacao ao File Converter do Livox Viewer 0.11.0:
- Livox Viewer 0.11.0: Point Format 2 (sem GPS time) — INADEQUADO
- Este conversor:     Point Format 3 (com GPS time)  — adequado para
                      fusao posterior com trajetoria GNSS (.ubx)

Uso:
    python lvx_to_las_ajr.py input.lvx [--output output.las] [--max-frames N]
    python lvx_to_las_ajr.py input.lvx --chunk-frames 100   (ajustar bloco)

AJR Security
"""

import sys
import struct
import os
import datetime
import argparse
from pathlib import Path

try:
    import numpy as np
    import laspy
except ImportError as e:
    print(f"ERRO: biblioteca faltando — {e}")
    print("Instalar com: pip install laspy numpy")
    sys.exit(1)


# ============================================================
# CONSTANTES (copiadas de analyze_lvx_v2.5.py)
# ============================================================

PACKAGE_HEADER_SIZE = 19

# Mapa de data_type -> (entries_por_package, bytes_por_entry, descricao)
#
# >>> ATENCAO — LEIA ISTO ANTES DE "CORRIGIR" OS NUMEROS <<<
#
# Os dois numeros descrevem coisas DIFERENTES e ambos estao corretos:
#   - 1o numero = quantas ENTRIES (blocos de bytes) o package contem
#   - 2o numero = quantos BYTES cada entry ocupa
#
# Para SINGLE return (data_type 2/3): 1 entry = 1 ponto.
#   Ex: data_type 2 -> (96, 14) -> 96 entries x 14 bytes -> 96 pontos.
#
# Para DUAL return (data_type 4/5): 1 entry = 2 pontos (retorno 1 + retorno 2).
#   Ex: data_type 4 -> (48, 28) -> 48 entries x 28 bytes -> 48 entries.
#       Mas cada entry de 28 bytes contem 2 pontos de 14 bytes:
#         [x1 y1 z1 ref1 tag1] (14 bytes) + [x2 y2 z2 ref2 tag2] (14 bytes)
#       Logo o package gera 48 x 2 = 96 PONTOS reais.
#
# Para TRIPLE return (data_type 7/8): 1 entry = 3 pontos.
#   Ex: data_type 7 -> (32, 42) -> 32 entries x 42 bytes -> 32 x 3 = 96 pontos.
#
# Conclusao: o numero de ENTRIES (usado para fatiar o payload) NAO eh igual
# ao numero de PONTOS quando ha multiplos retornos. O decode_points() abaixo
# expande cada entry no numero certo de pontos. Isso NAO eh bug nem "hibrido".
#
# (points_per_package_AS_ENTRIES, bytes_per_entry, description)
POINT_SIZES_AND_COUNTS = {
    0: (100, 13, "Cartesian single return (MID only)"),
    1: (100, 9,  "Spherical single return (MID only)"),
    2: (96,  14, "Cartesian single return - Avia/Horizon"),
    3: (96,  10, "Spherical single return - Avia/Horizon"),
    4: (48,  28, "Cartesian DUAL return (cada entry = 2 pontos)"),
    5: (48,  20, "Spherical DUAL return (cada entry = 2 pontos)"),
    6: (1,   24, "IMU data"),
    7: (32,  42, "Cartesian TRIPLE return (cada entry = 3 pontos)"),
    8: (32,  30, "Spherical TRIPLE return (cada entry = 3 pontos)"),
}


# ============================================================
# CONVERSAO DE TIMESTAMP
# ============================================================

GPS_EPOCH = datetime.datetime(1980, 1, 6, tzinfo=datetime.timezone.utc)
LEAP_SECONDS = 18
UNIX_TO_GPS_EPOCH = 315964800
GPS_ADJUSTED_OFFSET = 1_000_000_000


def utc_ns_to_gps_adjusted(utc_ns):
    """
    Converte UTC ns (desde 1970-01-01) para Adjusted GPS Time (LAS Format 3).

    Adjusted GPS Time = GPS Standard Time - 1e9
    GPS Standard Time = UTC seconds - 315964800 + leap_seconds
    """
    utc_seconds = utc_ns / 1e9
    gps_standard = utc_seconds - UNIX_TO_GPS_EPOCH + LEAP_SECONDS
    gps_adjusted = gps_standard - GPS_ADJUSTED_OFFSET
    return gps_adjusted
# DECODE DE PONTOS POR DATA_TYPE
# ============================================================

def decode_points(payload, data_type, num_points, bytes_per_point):
    """
    Decodifica o payload de um package em arrays numpy.

    Returns: (xs, ys, zs, intensities) em metros e 0-255

    NAO inclui filtro de zerados — quem chama decide.
    """
    if data_type == 4:
        # Cartesian DUAL return: 48 entries de 28 bytes cada
        # Cada entry contem 2 pontos com a seguinte estrutura:
        #   x1(4) + y1(4) + z1(4) + reflectivity1(1) + tag1(1)
        #   x2(4) + y2(4) + z2(4) + reflectivity2(1) + tag2(1)
        # Total: 14 + 14 = 28 bytes
        # 48 entries × 2 pontos = 96 pontos por package
        xs = []
        ys = []
        zs = []
        intensities = []

        for i in range(num_points):
            offset = i * bytes_per_point
            # Primeiro retorno
            x1, y1, z1, ref1, tag1 = struct.unpack('<iiiBB', payload[offset:offset+14])
            # Segundo retorno
            x2, y2, z2, ref2, tag2 = struct.unpack('<iiiBB', payload[offset+14:offset+28])

            xs.append(x1)
            ys.append(y1)
            zs.append(z1)
            intensities.append(ref1)

            xs.append(x2)
            ys.append(y2)
            zs.append(z2)
            intensities.append(ref2)

        # Converter mm para metros
        xs_m = np.array(xs, dtype=np.float64) / 1000.0
        ys_m = np.array(ys, dtype=np.float64) / 1000.0
        zs_m = np.array(zs, dtype=np.float64) / 1000.0
        ints = np.array(intensities, dtype=np.uint16)

        return xs_m, ys_m, zs_m, ints

    elif data_type == 2:
        # Cartesian single return (Avia/Horizon): 96 pontos × 14 bytes
        # x(4) + y(4) + z(4) + reflectivity(1) + tag(1)
        xs = []
        ys = []
        zs = []
        intensities = []

        for i in range(num_points):
            offset = i * bytes_per_point
            x, y, z, ref, tag = struct.unpack('<iiiBB', payload[offset:offset+14])
            xs.append(x)
            ys.append(y)
            zs.append(z)
            intensities.append(ref)

        xs_m = np.array(xs, dtype=np.float64) / 1000.0
        ys_m = np.array(ys, dtype=np.float64) / 1000.0
        zs_m = np.array(zs, dtype=np.float64) / 1000.0
        ints = np.array(intensities, dtype=np.uint16)

        return xs_m, ys_m, zs_m, ints

    elif data_type == 0:
        # Cartesian single return (MID): 100 pontos × 13 bytes
        # x(4) + y(4) + z(4) + reflectivity(1)
        xs = []
        ys = []
        zs = []
        intensities = []

        for i in range(num_points):
            offset = i * bytes_per_point
            x, y, z, ref = struct.unpack('<iiiB', payload[offset:offset+13])
            xs.append(x)
            ys.append(y)
            zs.append(z)
            intensities.append(ref)

        xs_m = np.array(xs, dtype=np.float64) / 1000.0
        ys_m = np.array(ys, dtype=np.float64) / 1000.0
        zs_m = np.array(zs, dtype=np.float64) / 1000.0
        ints = np.array(intensities, dtype=np.uint16)

        return xs_m, ys_m, zs_m, ints

    elif data_type == 7:
        # Cartesian TRIPLE return: 32 entries × 42 bytes
        # Cada entry contem 3 pontos
        xs = []
        ys = []
        zs = []
        intensities = []

        for i in range(num_points):
            offset = i * bytes_per_point
            x1, y1, z1, ref1, tag1 = struct.unpack('<iiiBB', payload[offset:offset+14])
            x2, y2, z2, ref2, tag2 = struct.unpack('<iiiBB', payload[offset+14:offset+28])
            x3, y3, z3, ref3, tag3 = struct.unpack('<iiiBB', payload[offset+28:offset+42])

            xs.extend([x1, x2, x3])
            ys.extend([y1, y2, y3])
            zs.extend([z1, z2, z3])
            intensities.extend([ref1, ref2, ref3])

        xs_m = np.array(xs, dtype=np.float64) / 1000.0
        ys_m = np.array(ys, dtype=np.float64) / 1000.0
        zs_m = np.array(zs, dtype=np.float64) / 1000.0
        ints = np.array(intensities, dtype=np.uint16)

        return xs_m, ys_m, zs_m, ints

    else:
        # Spherical ou outros — nao implementado nesta versao
        return None, None, None, None


# ============================================================
# CHUNKED LAS WRITER — escrita incremental (uso de RAM constante)
# ============================================================

class ChunkedLasWriter:
    """
    Escreve um .las Point Format 3 em blocos, sem acumular tudo na RAM.

    Estrategia de offset/escala:
      - Escala fixa milimetrica (0.001).
      - Offset fixo em (0,0,0). Como as coordenadas LOCAIS do Avia ficam
        em ~[-450, +450] m, com escala 0.001 os valores int32 vao a
        ~450.000 — muito dentro do limite de int32 (+-2.147e9). Seguro.
      - Offset fixo (em vez de min XYZ) eh o que permite streaming: nao
        precisamos conhecer o minimo antes de comecar a escrever.

    Uso:
        w = ChunkedLasWriter(output_path)
        w.append(xs, ys, zs, ints, gps)   # chamar N vezes
        w.close()
    """

    def __init__(self, output_path):
        self.output_path = Path(output_path)
        self.header = laspy.LasHeader(point_format=3, version="1.2")
        self.header.global_encoding.gps_time_type = 1  # Adjusted GPS Time
        self.header.scales = np.array([0.001, 0.001, 0.001])
        self.header.offsets = np.array([0.0, 0.0, 0.0])  # fixo p/ streaming

        # Abrir writer incremental do laspy
        self.writer = laspy.open(str(self.output_path), mode='w',
                                 header=self.header)

        # Stats acumuladas (sem guardar os pontos)
        self.n_written = 0
        self.x_min = None
        self.x_max = None
        self.y_min = None
        self.y_max = None
        self.z_min = None
        self.z_max = None
        self.gps_min = None
        self.gps_max = None

    def append(self, xs, ys, zs, ints, gps_time):
        """Escreve um bloco de pontos. Arrays numpy de mesmo tamanho.

        Usa laspy.LasData por bloco (API estavel desde laspy 2.0),
        em vez de ScaleAwarePointRecord.zeros (assinatura varia entre
        versoes do laspy). Isso garante compatibilidade cross-version.
        """
        n = len(xs)
        if n == 0:
            return

        # LasData temporario compartilhando o MESMO header (escala/offset/format)
        chunk = laspy.LasData(self.header)

        # Atribuir coordenadas (laspy aplica escala/offset automaticamente)
        chunk.x = xs
        chunk.y = ys
        chunk.z = zs

        ints_u16 = ints.astype(np.uint16)
        chunk.intensity = ints_u16
        chunk.gps_time = gps_time

        # RGB derivado da intensidade (cinza 16-bit)
        rgb = ints_u16 * 257
        chunk.red = rgb
        chunk.green = rgb
        chunk.blue = rgb

        # write_points aceita o PackedPointRecord do LasData
        self.writer.write_points(chunk.points)

        # Atualizar stats incrementais
        self.n_written += n
        bx_min, bx_max = float(xs.min()), float(xs.max())
        by_min, by_max = float(ys.min()), float(ys.max())
        bz_min, bz_max = float(zs.min()), float(zs.max())
        bg_min, bg_max = float(gps_time.min()), float(gps_time.max())

        self.x_min = bx_min if self.x_min is None else min(self.x_min, bx_min)
        self.x_max = bx_max if self.x_max is None else max(self.x_max, bx_max)
        self.y_min = by_min if self.y_min is None else min(self.y_min, by_min)
        self.y_max = by_max if self.y_max is None else max(self.y_max, by_max)
        self.z_min = bz_min if self.z_min is None else min(self.z_min, bz_min)
        self.z_max = bz_max if self.z_max is None else max(self.z_max, bz_max)
        self.gps_min = bg_min if self.gps_min is None else min(self.gps_min, bg_min)
        self.gps_max = bg_max if self.gps_max is None else max(self.gps_max, bg_max)

    def close(self):
        self.writer.close()


# ============================================================
# PARSER LVX + CHUNKED WRITE (logica de parsing copiada de v2.5)
# ============================================================

def parse_and_write_lvx(filepath, output_path, max_frames=None,
                        chunk_frames=100, verbose=True):
    """
    Le .lvx e escreve .las em blocos (chunked) sem acumular tudo na RAM.

    chunk_frames: a cada quantos frames descarregar o buffer para o disco.
                  100 frames (~5s a 20Hz) = buffer pequeno e seguro.

    Returns: dict com stats, ou None se nenhum ponto valido.
    """
    filesize = os.path.getsize(filepath)

    if verbose:
        print(f"Lendo {Path(filepath).name} ({filesize / 1e6:.1f} MB)...")

    writer = ChunkedLasWriter(output_path)

    # Buffers temporarios (descarregados a cada chunk_frames)
    buf_x, buf_y, buf_z, buf_i, buf_g = [], [], [], [], []

    def flush_buffer():
        """Descarrega buffer atual para o disco e limpa."""
        if not buf_x:
            return
        xs = np.concatenate(buf_x)
        ys = np.concatenate(buf_y)
        zs = np.concatenate(buf_z)
        ii = np.concatenate(buf_i)
        gg = np.concatenate(buf_g)
        writer.append(xs, ys, zs, ii, gg)
        buf_x.clear(); buf_y.clear(); buf_z.clear()
        buf_i.clear(); buf_g.clear()

    frame_count = 0
    total_imu = 0
    total_points_raw = 0
    total_points_kept = 0
    ts_type_3_count = 0
    ts_type_other_count = 0

    with open(filepath, 'rb') as f:
        # ---- Headers: public (24) + private (5) + device info ----
        # Validacao do public header
        sig = f.read(16)
        if not sig.startswith(b'livox_tech'):
            if verbose:
                print(f"  AVISO: assinatura inesperada: {sig[:10]}")
        ver = f.read(4)
        magic_bytes = f.read(4)
        try:
            magic_code = struct.unpack('<I', magic_bytes)[0]
        except struct.error:
            magic_code = 0

        if verbose:
            print(f"  Signature: {sig[:10].decode(errors='replace')}")
            print(f"  Version:   {ver[0]}.{ver[1]}.{ver[2]}.{ver[3]}")
            print(f"  Magic:     0x{magic_code:08X}")

        # Private header (5 bytes): frame_duration(4) + device_count(1)
        frame_duration = struct.unpack('<I', f.read(4))[0]
        device_count = struct.unpack('<B', f.read(1))[0]

        if verbose:
            print(f"  Frame duration: {frame_duration} ms")
            print(f"  Device count:   {device_count}")

        # Device info blocks (59 bytes cada)
        for i in range(device_count):
            dev = f.read(59)
            if len(dev) < 59:
                break
            lidar_sn = dev[0:16].decode(errors='replace').rstrip('\x00')
            device_type = dev[33] if len(dev) > 33 else '?'
            if verbose:
                print(f"  Device #{i}: SN={lidar_sn}, Type={device_type}")

        data_block_start = f.tell()

        if verbose:
            print(f"\nProcessando frames a partir do offset {data_block_start}...")
            print(f"  (chunked write: descarregando a cada {chunk_frames} frames)")

        current_pos = data_block_start

        while current_pos < filesize:
            if max_frames is not None and frame_count >= max_frames:
                break

            f.seek(current_pos)

            # ---- FRAME HEADER (24 bytes) ----
            try:
                fhdr = f.read(24)
                if len(fhdr) < 24:
                    break
                current_offset = struct.unpack('<Q', fhdr[0:8])[0]
                next_offset = struct.unpack('<Q', fhdr[8:16])[0]
                frame_index = struct.unpack('<Q', fhdr[16:24])[0]
            except Exception as e:
                if verbose:
                    print(f"  Falha ao ler frame header em {current_pos}: {e}")
                break

            if next_offset == 0 or next_offset <= current_pos:
                break
            if next_offset > filesize:
                break

            # Iterar packages dentro do frame
            pkg_start = current_pos + 24
            pkg_end = next_offset
            f.seek(pkg_start)
            bytes_remaining = pkg_end - pkg_start

            while bytes_remaining >= PACKAGE_HEADER_SIZE:
                pkg_bytes = f.read(PACKAGE_HEADER_SIZE)
                if len(pkg_bytes) < PACKAGE_HEADER_SIZE:
                    break

                ts_type = pkg_bytes[9]
                data_type = pkg_bytes[10]

                # Decodificar timestamp
                if ts_type == 3:
                    year = pkg_bytes[11]
                    month = pkg_bytes[12]
                    day = pkg_bytes[13]
                    hour = pkg_bytes[14]
                    us_within_hour = struct.unpack('<I', pkg_bytes[15:19])[0]
                    try:
                        full_year = 2000 + year if year < 100 else year
                        dt = datetime.datetime(full_year, month, day, hour, 0, 0,
                                               tzinfo=datetime.timezone.utc)
                        epoch_seconds = dt.timestamp()
                        timestamp_ns = int(epoch_seconds * 1e9 + us_within_hour * 1000)
                        gps_adj = utc_ns_to_gps_adjusted(timestamp_ns)
                    except (ValueError, OSError):
                        gps_adj = None
                    ts_type_3_count += 1
                else:
                    gps_adj = None
                    ts_type_other_count += 1

                bytes_remaining -= PACKAGE_HEADER_SIZE

                # Ler payload
                if data_type in POINT_SIZES_AND_COUNTS:
                    pts_per_pkg, bytes_per_pt, _ = POINT_SIZES_AND_COUNTS[data_type]
                    payload_size = pts_per_pkg * bytes_per_pt

                    if data_type == 6:
                        total_imu += 1
                        if bytes_remaining < payload_size:
                            break
                        f.read(payload_size)
                        bytes_remaining -= payload_size
                        continue

                    if bytes_remaining < payload_size:
                        break

                    payload = f.read(payload_size)
                    bytes_remaining -= payload_size

                    if gps_adj is not None:
                        xs, ys, zs, ints = decode_points(payload, data_type,
                                                         pts_per_pkg, bytes_per_pt)
                        if xs is not None:
                            mask = ~((xs == 0) & (ys == 0) & (zs == 0))
                            n_total = len(xs)
                            n_kept = int(np.sum(mask))

                            total_points_raw += n_total
                            total_points_kept += n_kept

                            if n_kept > 0:
                                buf_x.append(xs[mask])
                                buf_y.append(ys[mask])
                                buf_z.append(zs[mask])
                                buf_i.append(ints[mask])
                                buf_g.append(np.full(n_kept, gps_adj,
                                                     dtype=np.float64))
                else:
                    if verbose:
                        print(f"  Frame {frame_index}: data_type desconhecido "
                              f"{data_type}, pulando frame")
                    break

            frame_count += 1
            current_pos = next_offset

            # Descarregar buffer periodicamente (CHUNKED WRITE)
            if frame_count % chunk_frames == 0:
                flush_buffer()
                if verbose:
                    print(f"  Frames: {frame_count} | "
                          f"Pontos escritos: {writer.n_written:,}")

        # Descarregar o que sobrou
        flush_buffer()

    writer.close()

    if verbose:
        print(f"\nProcessamento concluido:")
        print(f"  Frames:              {frame_count}")
        print(f"  Pontos raw:          {total_points_raw:,}")
        print(f"  Pontos validos:      {total_points_kept:,}")
        print(f"  Pacotes IMU:         {total_imu:,}")
        print(f"  Packages ts_type=3:  {ts_type_3_count:,}")
        print(f"  Packages outros:     {ts_type_other_count:,}")

    if writer.n_written == 0:
        # Remover arquivo vazio
        try:
            Path(output_path).unlink()
        except OSError:
            pass
        return None

    return {
        'n_points': writer.n_written,
        'x_min': writer.x_min, 'x_max': writer.x_max,
        'y_min': writer.y_min, 'y_max': writer.y_max,
        'z_min': writer.z_min, 'z_max': writer.z_max,
        'gps_min': writer.gps_min, 'gps_max': writer.gps_max,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Converte .lvx para .las Point Format 3 com GPS time (chunked)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python lvx_to_las_ajr.py arquivo.lvx
  python lvx_to_las_ajr.py arquivo.lvx -o saida.las
  python lvx_to_las_ajr.py arquivo.lvx --max-frames 10
  python lvx_to_las_ajr.py arquivo.lvx --chunk-frames 200

v3.0: escrita chunked (uso de RAM constante, suporta voos longos)
"""
    )
    parser.add_argument('input', type=str, help='Arquivo .lvx de entrada')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Saida .las (padrao: <input>_local.las)')
    parser.add_argument('--max-frames', type=int, default=None,
                        help='Limite de frames para teste rapido')
    parser.add_argument('--chunk-frames', type=int, default=100,
                        help='Frames por bloco de escrita (padrao: 100)')
    parser.add_argument('--quiet', action='store_true', help='Modo silencioso')

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERRO: arquivo nao encontrado: {input_path}")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + '_local.las')

    verbose = not args.quiet

    print("=" * 60)
    print("lvx_to_las_ajr v3.1 — AJR Security (chunked)")
    print("=" * 60)
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    if args.max_frames:
        print(f"Mode:   TESTE — apenas {args.max_frames} frames")
    print()

    stats = parse_and_write_lvx(str(input_path), output_path,
                                max_frames=args.max_frames,
                                chunk_frames=args.chunk_frames,
                                verbose=verbose)

    if stats is None:
        print("\nERRO: nenhum ponto valido encontrado.")
        print("  Possiveis causas:")
        print("  - .lvx sem GPS sync (timestamp_type != 3)")
        print("  - Arquivo corrompido")
        sys.exit(1)

    if verbose:
        print(f"\nArquivo salvo: {output_path}")
        print(f"  Tamanho:        {output_path.stat().st_size / 1e6:.1f} MB")
        print(f"  Pontos:         {stats['n_points']:,}")
        print(f"  X range:        {stats['x_min']:.3f} a {stats['x_max']:.3f} m")
        print(f"  Y range:        {stats['y_min']:.3f} a {stats['y_max']:.3f} m")
        print(f"  Z range:        {stats['z_min']:.3f} a {stats['z_max']:.3f} m")
        print(f"  GPS time min:   {stats['gps_min']:.3f}")
        print(f"  GPS time max:   {stats['gps_max']:.3f}")
        print(f"  GPS time delta: {stats['gps_max'] - stats['gps_min']:.3f} s")

    print()
    print("=" * 60)
    print("CONVERSAO CONCLUIDA")
    print("=" * 60)


if __name__ == '__main__':
    main()
