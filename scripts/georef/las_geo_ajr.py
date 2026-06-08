#!/usr/bin/env python3
"""
las_geo_ajr.py v1.2
=======================

Aplica trajetoria GNSS (de arquivo .ubx) a uma nuvem .las local
para gerar nuvem aproximadamente georreferenciada.

v1.2 (28/05/2026): Robustez (revisao externa). Ajustes:
                   - Valida que input e Point Format 3 (contrato de entrada)
                   - RGB copiado so se existir no LAS de origem
                   - parsed.nano com clamp defensivo (0..999999 us)
                   - except logando erro quando verbose (nao silencia mais)
                   - Removido GPS_EPOCH unused
                   VERSAO CONGELADA — proximo passo e voo real, nao codigo.
v1.1 (28/05/2026): CORRECAO de bug latente de timezone — o timestamp do
                   NAV-PVT era construido sem tzinfo, fazendo .timestamp()
                   assumir horario local. Em maquina fora de UTC (ex: Brasilia
                   UTC-3) isso deslocaria a trajetoria em horas e quebraria o
                   overlap temporal. Agora forca tzinfo=timezone.utc.
v1.0 (26/05/2026): Versao inicial.

LIMITACOES IMPORTANTES:
  - Aplica APENAS translacao (posicao do drone interpolada por timestamp)
  - NAO aplica rotacao do drone (roll/pitch/yaw)
  - NAO aplica lever-arm (offset antena GNSS <-> sensor LiDAR)
  - NAO aplica boresight (alinhamento angular sensor <-> aeronave)
  - Erro esperado: metros, nao centimetros

Saida em coordenadas UTM (zona configuravel).

Uso:
    python las_geo_ajr.py input_local.las gnss.ubx [--output out.las]
                              [--utm-zone N] [--hemisphere south|north]

Exemplo:
    python las_geo_ajr.py 2026-05-26_16-18-16_local.las gnss.ubx \\
                              --utm-zone 22 --hemisphere south

AJR Security
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

try:
    import numpy as np
    import laspy
    from pyubx2 import UBXReader
    import pyproj
except ImportError as e:
    print(f"ERRO: biblioteca faltando — {e}")
    print("Instalar com: pip install laspy numpy pyubx2 pyproj")
    sys.exit(1)


# ============================================================
# CONSTANTES (conversao GPS time)
# ============================================================

LEAP_SECONDS = 18
UNIX_TO_GPS_EPOCH = 315964800
GPS_ADJUSTED_OFFSET = 1_000_000_000


def gps_adjusted_to_unix(gps_adj):
    """Converte Adjusted GPS Time (LAS) para Unix time."""
    gps_standard = gps_adj + GPS_ADJUSTED_OFFSET
    unix_seconds = gps_standard + UNIX_TO_GPS_EPOCH - LEAP_SECONDS
    return unix_seconds


# ============================================================
# EXTRAIR TRAJETORIA DO .UBX
# ============================================================

def extract_trajectory(ubx_path, verbose=True):
    """
    Extrai trajetoria do .ubx como arrays numpy.

    Returns: dict com 't_unix', 'lat', 'lon', 'alt'
    """
    if verbose:
        print(f"Lendo trajetoria de {Path(ubx_path).name}...")

    timestamps = []
    lats = []
    lons = []
    alts = []
    fix_count = 0
    nofix_count = 0

    with open(ubx_path, 'rb') as f:
        reader = UBXReader(f, protfilter=2)
        for raw, parsed in reader:
            if not parsed or not hasattr(parsed, 'identity'):
                continue
            if parsed.identity != 'NAV-PVT':
                continue

            try:
                if parsed.fixType >= 3:
                    # Timestamp Unix (UTC)
                    # CRITICO: tzinfo=timezone.utc e obrigatorio. Sem isso,
                    # datetime.timestamp() assume horario LOCAL da maquina e
                    # introduz erro igual ao offset do fuso (ex: -3h em Brasilia),
                    # quebrando o overlap temporal com o LAS (que e UTC).
                    # Clamp defensivo do nano -> microssegundos (0..999999)
                    micro = max(0, min(999999, parsed.nano // 1000))
                    ts = datetime(parsed.year, parsed.month, parsed.day,
                                  parsed.hour, parsed.min, parsed.second,
                                  micro, tzinfo=timezone.utc)
                    t_unix = ts.timestamp()

                    # pyubx2 entrega lat/lon ja em graus decimais
                    timestamps.append(t_unix)
                    lats.append(parsed.lat)
                    lons.append(parsed.lon)
                    alts.append(parsed.hMSL / 1000.0)  # mm -> m
                    fix_count += 1
                else:
                    nofix_count += 1
            except Exception as e:
                # NAO silenciar: NAV-PVT malformado pode esconder bug.
                # Continua processando, mas registra quando verbose.
                if verbose:
                    print(f"  AVISO: NAV-PVT ignorado por erro: {e}")

    if verbose:
        print(f"  NAV-PVT com fix 3D: {fix_count}")
        print(f"  NAV-PVT sem fix:    {nofix_count}")

    if fix_count < 2:
        raise ValueError(f"Trajetoria insuficiente: apenas {fix_count} pontos com fix")

    # Converter para arrays e ordenar por tempo
    t_arr = np.array(timestamps, dtype=np.float64)
    sort_idx = np.argsort(t_arr)

    return {
        't_unix': t_arr[sort_idx],
        'lat': np.array(lats, dtype=np.float64)[sort_idx],
        'lon': np.array(lons, dtype=np.float64)[sort_idx],
        'alt': np.array(alts, dtype=np.float64)[sort_idx],
    }


# ============================================================
# GEORREFERENCIAR
# ============================================================

def georeference_las(las_path, traj, utm_zone, hemisphere, output_path, verbose=True):
    """
    Aplica trajetoria (translacao simples) aos pontos do .las.
    Gera .las georreferenciado em UTM.
    """
    if verbose:
        print(f"\nLendo {Path(las_path).name}...")

    las = laspy.read(las_path)

    # Point Format 3 e CONTRATO DE ENTRADA deste pipeline.
    # O conversor AJR sempre gera Format 3 (gps_time + RGB).
    # Nao herdamos o formato do input de propósito: formatos do Livox
    # Viewer (ex: Format 2) podem nao preservar gps_time, e formatos
    # LAS 1.4 (6/7/8) mudam a estrutura de gps_time_type e RGB.
    if las.header.point_format.id != 3:
        raise ValueError(
            f"LAS input e Point Format {las.header.point_format.id}, "
            f"mas este pipeline exige Point Format 3 gerado pelo conversor "
            f"AJR (lvx_to_las_ajr). Formatos do Livox Viewer nao "
            f"servem porque podem nao preservar gps_time."
        )

    if 'gps_time' not in las.point_format.dimension_names:
        raise ValueError("LAS sem gps_time — nao da para sincronizar")

    n_points = len(las.points)
    if verbose:
        print(f"  Pontos: {n_points:,}")
        print(f"  Point format: {las.header.point_format.id}")
        print(f"  GPS time type: {las.header.global_encoding.gps_time_type}")

    # ----- 1. Converter GPS time do LAS para Unix time -----
    if verbose:
        print(f"\nConvertendo GPS time (Adjusted) -> Unix time...")

    if las.header.global_encoding.gps_time_type != 1:
        print(f"  AVISO: GPS time type = {las.header.global_encoding.gps_time_type}")
        print(f"         Esperado 1 (Adjusted). Pode haver erro de conversao.")

    las_t_unix = gps_adjusted_to_unix(las.gps_time)

    if verbose:
        print(f"  LAS Unix time range:  {las_t_unix.min():.3f} a {las_t_unix.max():.3f}")
        print(f"  Traj Unix time range: {traj['t_unix'].min():.3f} a {traj['t_unix'].max():.3f}")

    # ----- 2. Validar overlap temporal -----
    overlap_start = max(las_t_unix.min(), traj['t_unix'].min())
    overlap_end = min(las_t_unix.max(), traj['t_unix'].max())

    if overlap_end <= overlap_start:
        raise ValueError(
            f"Sem overlap temporal entre LAS e trajetoria.\n"
            f"  LAS:  {las_t_unix.min()} a {las_t_unix.max()}\n"
            f"  Traj: {traj['t_unix'].min()} a {traj['t_unix'].max()}"
        )

    if verbose:
        overlap_dur = overlap_end - overlap_start
        las_dur = las_t_unix.max() - las_t_unix.min()
        pct_covered = 100.0 * overlap_dur / las_dur
        print(f"  Overlap: {overlap_dur:.1f} s ({pct_covered:.1f}% do LAS)")

    # ----- 3. Setup projecao UTM -----
    if verbose:
        print(f"\nProjetando para UTM Zone {utm_zone}{hemisphere.upper()[0]}...")

    wgs84 = pyproj.CRS('EPSG:4326')
    if hemisphere == 'south':
        utm = pyproj.CRS(f'EPSG:327{utm_zone:02d}')
    else:
        utm = pyproj.CRS(f'EPSG:326{utm_zone:02d}')
    transformer = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True)

    traj_utm_x, traj_utm_y = transformer.transform(traj['lon'], traj['lat'])

    if verbose:
        print(f"  UTM trajetoria centro:")
        print(f"    X: {np.mean(traj_utm_x):,.2f}")
        print(f"    Y: {np.mean(traj_utm_y):,.2f}")
        print(f"    Z: {np.mean(traj['alt']):,.2f}")

    # ----- 4. Interpolar posicao do drone para cada ponto LiDAR -----
    if verbose:
        print(f"\nInterpolando posicao do drone para {n_points:,} pontos...")

    # Clipar timestamps dos pontos LiDAR ao intervalo da trajetoria
    # (evita extrapolacao em pontos fora do overlap)
    t_clipped = np.clip(las_t_unix, traj['t_unix'].min(), traj['t_unix'].max())

    drone_x = np.interp(t_clipped, traj['t_unix'], traj_utm_x)
    drone_y = np.interp(t_clipped, traj['t_unix'], traj_utm_y)
    drone_z = np.interp(t_clipped, traj['t_unix'], traj['alt'])

    # ----- 5. Aplicar translacao simples -----
    if verbose:
        print(f"\nAplicando translacao simples...")
        print(f"  AVISO: nao aplica rotacao do drone (roll/pitch/yaw)")
        print(f"         nao aplica lever-arm")
        print(f"         erro esperado: metros")

    # Coordenadas LiDAR locais (em metros relativos ao sensor)
    local_x = np.array(las.x, dtype=np.float64)
    local_y = np.array(las.y, dtype=np.float64)
    local_z = np.array(las.z, dtype=np.float64)

    # Translacao
    global_x = drone_x + local_x
    global_y = drone_y + local_y
    global_z = drone_z + local_z

    # ----- 6. Criar novo LAS georreferenciado -----
    if verbose:
        print(f"\nEscrevendo {output_path.name}...")

    # Header novo com escala UTM
    new_header = laspy.LasHeader(point_format=3, version="1.2")
    new_header.global_encoding.gps_time_type = 1

    # Escala mantida (mm)
    new_header.scales = np.array([0.001, 0.001, 0.001])
    new_header.offsets = np.array([
        float(np.min(global_x)),
        float(np.min(global_y)),
        float(np.min(global_z))
    ])

    new_las = laspy.LasData(new_header)
    new_las.x = global_x
    new_las.y = global_y
    new_las.z = global_z
    new_las.intensity = las.intensity
    new_las.gps_time = las.gps_time

    # RGB copiado apenas se existir no LAS de origem (defensivo).
    # Format 3 sempre tem, mas validamos para nao quebrar com
    # AttributeError se algum dia o input variar.
    src_dims = las.point_format.dimension_names
    if all(c in src_dims for c in ('red', 'green', 'blue')):
        new_las.red = las.red
        new_las.green = las.green
        new_las.blue = las.blue

    new_las.write(output_path)

    if verbose:
        print(f"\nArquivo salvo: {output_path}")
        print(f"  Tamanho:  {output_path.stat().st_size / 1e6:.1f} MB")
        print(f"  Pontos:   {n_points:,}")
        print(f"  X (UTM):  {global_x.min():,.2f} a {global_x.max():,.2f}")
        print(f"  Y (UTM):  {global_y.min():,.2f} a {global_y.max():,.2f}")
        print(f"  Z (alt):  {global_z.min():,.2f} a {global_z.max():,.2f}")

        # Converter centro de volta para lat/lon para reportar
        utm_to_wgs = pyproj.Transformer.from_crs(utm, wgs84, always_xy=True)
        center_lon, center_lat = utm_to_wgs.transform(
            (global_x.min() + global_x.max()) / 2,
            (global_y.min() + global_y.max()) / 2
        )
        print(f"\n  Centro da nuvem em lat/lon:")
        print(f"    Lat: {center_lat:.6f}")
        print(f"    Lon: {center_lon:.6f}")
        print(f"    Google Maps: https://www.google.com/maps?q={center_lat},{center_lon}")

    return True


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Georreferencia .las local usando trajetoria do .ubx',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Padrao: UTM zona 22 sul (Florianopolis/SP)
  python las_geo_ajr.py local.las gnss.ubx

  # Outras zonas:
  # Acre: --utm-zone 19 --hemisphere south
  # Roraima: --utm-zone 20 --hemisphere north
  # Tocantins: --utm-zone 22 --hemisphere south
  # Manaus: --utm-zone 22 --hemisphere south

LIMITACOES:
  - Translacao simples — sem rotacao, lever-arm ou boresight
  - Erro esperado: metros (nao centimetros)
  - Adequado para: validar pipeline, conferir local no mapa
  - Inadequado para: entrega final ao cliente sem refinamento
"""
    )
    parser.add_argument('las', type=str, help='Arquivo .las local (coords sensor)')
    parser.add_argument('ubx', type=str, help='Arquivo .ubx com trajetoria GNSS')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Saida .las (padrao: <las>_geo.las)')
    parser.add_argument('--utm-zone', type=int, default=22,
                        help='Zona UTM (padrao: 22)')
    parser.add_argument('--hemisphere', type=str, default='south',
                        choices=['south', 'north'],
                        help='Hemisferio (padrao: south)')
    parser.add_argument('--quiet', action='store_true')

    args = parser.parse_args()

    las_path = Path(args.las)
    ubx_path = Path(args.ubx)

    if not las_path.exists():
        print(f"ERRO: LAS nao encontrado: {las_path}")
        sys.exit(1)
    if not ubx_path.exists():
        print(f"ERRO: UBX nao encontrado: {ubx_path}")
        sys.exit(1)

    if args.output:
        output_path = Path(args.output)
    else:
        # Padrao: <input>_geo.las
        stem = las_path.stem
        if stem.endswith('_local'):
            stem = stem[:-6]  # remove _local
        output_path = las_path.with_name(stem + '_geo.las')

    verbose = not args.quiet

    print("=" * 60)
    print("las_geo_ajr v1.2 — AJR Security")
    print("=" * 60)
    print(f"LAS in:  {las_path}")
    print(f"UBX in:  {ubx_path}")
    print(f"LAS out: {output_path}")
    print(f"UTM:     Zone {args.utm_zone}{args.hemisphere.upper()[0]}")
    print()
    print("ATENCAO: aplicando TRANSLACAO simples")
    print("         sem rotacao, lever-arm ou boresight")
    print("         erro esperado: metros")
    print()

    try:
        traj = extract_trajectory(str(ubx_path), verbose=verbose)
    except Exception as e:
        print(f"\nERRO extraindo trajetoria: {e}")
        sys.exit(1)

    try:
        georeference_las(str(las_path), traj, args.utm_zone, args.hemisphere,
                         output_path, verbose=verbose)
    except Exception as e:
        print(f"\nERRO na georeferenciacao: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("GEORREFERENCIAMENTO CONCLUIDO")
    print("=" * 60)
    print()
    print("Proximos passos:")
    print(f"  1. Abrir no CloudCompare:")
    print(f"     open -a CloudCompare {output_path}")
    print(f"  2. Verificar centro da nuvem no Google Maps (link acima)")
    print(f"  3. Avaliar se erro de metros e aceitavel para o caso de uso")


if __name__ == '__main__':
    main()
