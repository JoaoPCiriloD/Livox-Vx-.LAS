#!/usr/bin/env python3
"""
redtech_compare.py v1.0
=======================

Compara metricas de multiplas sessoes processadas pelo redtech_pipeline.py.

Le os arquivos metrics.json gerados pelo pipeline e produz tabela comparativa.

Uso:
    # Comparar TODAS as sessoes processadas
    python3 redtech_compare.py --all

    # Comparar sessoes especificas
    python3 redtech_compare.py voo_20260527_142555 voo_20260527_142428

    # Salvar resultado em arquivo
    python3 redtech_compare.py --all --output comparacao.md

    # Pasta de sessoes diferente
    python3 redtech_compare.py --all --sessoes ~/MyRedTech/sessoes

RedTech Security
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime


def load_session_metrics(session_dir):
    """Carrega metrics.json de uma pasta de sessao."""
    metrics_path = session_dir / "metrics.json"
    if not metrics_path.exists():
        return None
    try:
        return json.loads(metrics_path.read_text())
    except Exception as e:
        print(f"AVISO: erro lendo {metrics_path}: {e}", file=sys.stderr)
        return None


def find_all_sessions(sessoes_dir):
    """Retorna lista de pastas de sessao que tem metrics.json."""
    sessoes_dir = Path(sessoes_dir)
    if not sessoes_dir.is_dir():
        return []

    sessions = []
    for child in sorted(sessoes_dir.iterdir()):
        if child.is_dir() and (child / "metrics.json").exists():
            sessions.append(child)
    return sessions


def format_table(rows, headers, alignment=None):
    """
    Formata tabela markdown.
    rows: list of lists (cada interna eh uma linha)
    headers: list of strings
    alignment: list of 'left'|'right'|'center', mesmo tamanho que headers
    """
    if alignment is None:
        alignment = ['left'] * len(headers)

    lines = []

    # Header
    lines.append("| " + " | ".join(headers) + " |")

    # Separator
    seps = []
    for a in alignment:
        if a == 'right':
            seps.append("---:")
        elif a == 'center':
            seps.append(":---:")
        else:
            seps.append("---")
    lines.append("|" + "|".join(seps) + "|")

    # Rows
    for row in rows:
        cells = [str(c) if c is not None else "—" for c in row]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def compare_sessions(session_dirs):
    """Compara metricas de varias sessoes. Retorna string markdown."""

    sessions_data = []
    for sd in session_dirs:
        data = load_session_metrics(sd)
        if data:
            sessions_data.append((sd.name, data))

    if not sessions_data:
        return "# Comparacao\n\nNenhuma sessao encontrada com metrics.json."

    out = []
    out.append("# Comparacao de Sessoes RedTech")
    out.append("")
    out.append(f"**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"**Sessoes comparadas:** {len(sessions_data)}")
    out.append("")

    # ============ Sessoes incluidas ============
    out.append("## Sessoes Incluidas")
    out.append("")
    rows = []
    for name, data in sessions_data:
        m = data.get('metrics', {})
        lvx_start = m.get('lvx_start', '—')
        if lvx_start != '—' and lvx_start:
            # Pega so HH:MM:SS
            try:
                dt = datetime.fromisoformat(lvx_start)
                lvx_start = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            except Exception:
                pass

        criteria = data.get('criteria', [])
        n_pass = sum(1 for c in criteria if c[1] == 'pass')
        n_warn = sum(1 for c in criteria if c[1] == 'warn')
        n_fail = sum(1 for c in criteria if c[1] == 'fail')
        total = len(criteria)

        status = "OK" if n_fail == 0 else "FAIL"
        if n_fail == 0 and n_warn > 0:
            status = "WARN"

        rows.append([
            name,
            lvx_start,
            f"{n_pass}/{total}",
            n_warn,
            n_fail,
            status,
        ])

    out.append(format_table(
        rows,
        ["Sessao", "Inicio LVX (UTC)", "Pass", "Warn", "Fail", "Status"],
        ["left", "left", "center", "center", "center", "center"]
    ))
    out.append("")

    # ============ Metricas GNSS ============
    out.append("## GNSS (gnss.ubx)")
    out.append("")
    rows = []
    for name, data in sessions_data:
        m = data.get('metrics', {})
        rows.append([
            name,
            m.get('ubx_nav_pvt', '—'),
            m.get('ubx_fix_count', '—'),
            m.get('ubx_rxm_rawx', '—'),
            f"{m.get('ubx_sats_avg', 0):.1f}" if 'ubx_sats_avg' in m else '—',
            f"{m.get('ubx_pdop_avg', 0):.2f}" if 'ubx_pdop_avg' in m else '—',
            f"{m.get('ubx_hacc_avg', 0):.0f}mm" if 'ubx_hacc_avg' in m else '—',
            f"{m.get('ubx_duration', 0):.0f}s" if 'ubx_duration' in m else '—',
        ])

    out.append(format_table(
        rows,
        ["Sessao", "NAV-PVT", "Fix 3D", "RAWX", "Sats", "pDOP", "hAcc", "Duracao"],
        ["left", "right", "right", "right", "right", "right", "right", "right"]
    ))
    out.append("")

    # ============ Metricas LVX ============
    out.append("## LiDAR (lidar.lvx)")
    out.append("")
    rows = []
    for name, data in sessions_data:
        m = data.get('metrics', {})
        rows.append([
            name,
            f"{m.get('lvx_size_mb', 0):.1f}MB" if 'lvx_size_mb' in m else '—',
            m.get('lvx_frames', '—'),
            m.get('lvx_packages', '—'),
            f"{m.get('lvx_ts_type_3_pct', 0):.1f}%" if 'lvx_ts_type_3_pct' in m else '—',
            f"{m.get('lvx_duration', 0):.1f}s" if 'lvx_duration' in m else '—',
            f"{m.get('lvx_imu_rate', 0):.1f}Hz" if 'lvx_imu_rate' in m else '—',
            "Dual" if m.get('lvx_dual_return', 0) > m.get('lvx_single_return', 0) else "Single",
        ])

    out.append(format_table(
        rows,
        ["Sessao", "Tamanho", "Frames", "Packages", "ts=3", "Duracao", "IMU", "Modo"],
        ["left", "right", "right", "right", "right", "right", "right", "center"]
    ))
    out.append("")

    # ============ Cobertura temporal ============
    out.append("## Cobertura Temporal (UBX vs LVX)")
    out.append("")
    rows = []
    for name, data in sessions_data:
        m = data.get('metrics', {})
        ms = m.get('margin_start')
        me = m.get('margin_end')
        rows.append([
            name,
            f"{ms:+.1f}s" if ms is not None else '—',
            f"{me:+.1f}s" if me is not None else '—',
            "OK" if (ms is not None and me is not None and ms >= 0 and me >= 0) else "Apertado",
        ])

    out.append(format_table(
        rows,
        ["Sessao", "Margem inicio", "Margem fim", "Cobertura"],
        ["left", "right", "right", "center"]
    ))
    out.append("")

    # ============ Posicao e georef ============
    out.append("## Posicao (Centro da nuvem)")
    out.append("")
    rows = []
    for name, data in sessions_data:
        m = data.get('metrics', {})
        lat = m.get('geo_center_lat') or m.get('ubx_lat')
        lon = m.get('geo_center_lon') or m.get('ubx_lon')
        zmin = m.get('geo_z_min')
        zmax = m.get('geo_z_max')

        lat_str = f"{lat:.6f}" if lat is not None else '—'
        lon_str = f"{lon:.6f}" if lon is not None else '—'
        z_str = f"{zmin:.1f} a {zmax:.1f}m" if zmin is not None else '—'

        rows.append([
            name,
            lat_str,
            lon_str,
            z_str,
            m.get('las_local_points', '—'),
        ])

    out.append(format_table(
        rows,
        ["Sessao", "Lat", "Lon", "Z range", "Pontos validos"],
        ["left", "right", "right", "right", "right"]
    ))
    out.append("")

    # ============ Links Google Maps ============
    out.append("## Links Google Maps")
    out.append("")
    for name, data in sessions_data:
        m = data.get('metrics', {})
        lat = m.get('geo_center_lat') or m.get('ubx_lat')
        lon = m.get('geo_center_lon') or m.get('ubx_lon')
        if lat is not None and lon is not None:
            out.append(f"- **{name}:** "
                       f"https://www.google.com/maps?q={lat},{lon}")
    out.append("")

    # ============ Reconstrucao LIO ============
    out.append("## Reconstrucao de Trajetoria LiDAR-Inercial (LIO)")
    out.append("")
    out.append(
        "O pipeline agora gera tambem arquivos `_lio_geo.las`, aplicando "
        "orientacao estimada pela IMU do LVX antes da translacao GNSS/UTM. "
        "Esta etapa considera odometria inercial do LiDAR para reconstruir "
        "a trajetoria de orientacao do sensor. Um refinamento LIO completo "
        "com scan matching/ICP ainda pode ser feito com LIO-SAM ou FAST-LIO."
    )
    out.append("")

    rows = []
    for name, data in sessions_data:
        m = data.get('metrics', {})
        imu_rate = m.get('lvx_imu_rate')
        sync_pct = m.get('lvx_ts_type_3_pct')
        margin_start = m.get('margin_start')
        margin_end = m.get('margin_end')

        if 'lio_ready_inputs' in m:
            ready_inputs = m.get('lio_ready_inputs')
            lio_applied = m.get('lio_applied')
        else:
            ready_inputs = (
                imu_rate is not None and sync_pct is not None and
                margin_start is not None and margin_end is not None and
                imu_rate >= 150 and sync_pct >= 95 and
                margin_start >= -2 and margin_end >= -2
            )
            lio_applied = False

        rows.append([
            name,
            "Sim" if lio_applied else "Nao",
            "Sim" if ready_inputs else "Nao",
            f"{imu_rate:.1f}Hz" if imu_rate is not None else "—",
            f"{sync_pct:.1f}%" if sync_pct is not None else "—",
            "LIO-SAM / FAST-LIO",
        ])

    out.append(format_table(
        rows,
        ["Sessao", "LIO aplicada", "Entradas prontas", "IMU", "ts=3", "Proxima etapa"],
        ["left", "center", "center", "right", "right", "left"]
    ))
    out.append("")
    out.append(
        "Etapas tecnicas: sincronizacao temporal LiDAR/IMU, calibracao "
        "extrinseca, integracao inercial para previsao de pose, scan "
        "matching/ICP entre varreduras e correcao por EKF ou otimizacao em "
        "grafo de fatores."
    )
    out.append("")

    # ============ Diferencas entre sessoes consecutivas ============
    if len(sessions_data) >= 2:
        out.append("## Diferencas entre Sessoes Consecutivas")
        out.append("")
        out.append("Distancia (metros) entre centros das nuvens georreferenciadas.")
        out.append("")

        # Tentar import pyproj para calculo real
        try:
            import pyproj
            geod = pyproj.Geod(ellps='WGS84')

            rows = []
            for i in range(len(sessions_data) - 1):
                name_a, data_a = sessions_data[i]
                name_b, data_b = sessions_data[i+1]

                m_a = data_a.get('metrics', {})
                m_b = data_b.get('metrics', {})

                lat_a = m_a.get('geo_center_lat') or m_a.get('ubx_lat')
                lon_a = m_a.get('geo_center_lon') or m_a.get('ubx_lon')
                lat_b = m_b.get('geo_center_lat') or m_b.get('ubx_lat')
                lon_b = m_b.get('geo_center_lon') or m_b.get('ubx_lon')

                if all(v is not None for v in [lat_a, lon_a, lat_b, lon_b]):
                    _, _, dist = geod.inv(lon_a, lat_a, lon_b, lat_b)
                    rows.append([
                        name_a,
                        name_b,
                        f"{dist:.1f}m"
                    ])

            if rows:
                out.append(format_table(
                    rows,
                    ["Sessao A", "Sessao B", "Distancia"],
                    ["left", "left", "right"]
                ))
                out.append("")
        except ImportError:
            out.append("*(pyproj nao disponivel — distancias nao calculadas)*")
            out.append("")

    # ============ Footer ============
    out.append("---")
    out.append("")
    out.append("*Gerado por redtech_compare.py v1.0*")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(
        description='Comparar metricas de sessoes RedTech processadas',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Todas as sessoes
  python3 redtech_compare.py --all

  # Sessoes especificas
  python3 redtech_compare.py voo_20260527_142555 voo_20260527_142428

  # Salvar em arquivo
  python3 redtech_compare.py --all --output ~/comparacao.md
"""
    )
    parser.add_argument('sessions', nargs='*',
                        help='Nomes de sessoes (opcional, use --all para todas)')
    parser.add_argument('--all', action='store_true',
                        help='Comparar todas sessoes disponiveis')
    parser.add_argument('--sessoes', type=str, default='~/RedTech/sessoes',
                        help='Pasta raiz onde estao as sessoes processadas')
    parser.add_argument('--output', type=str, default=None,
                        help='Salvar saida em arquivo (default: stdout)')

    args = parser.parse_args()

    sessoes_root = Path(args.sessoes).expanduser()

    if args.all:
        session_dirs = find_all_sessions(sessoes_root)
        if not session_dirs:
            print(f"ERRO: nenhuma sessao encontrada em {sessoes_root}",
                  file=sys.stderr)
            sys.exit(1)
    elif args.sessions:
        session_dirs = []
        for name in args.sessions:
            sd = sessoes_root / name
            if not sd.exists():
                print(f"AVISO: sessao nao encontrada: {sd}", file=sys.stderr)
                continue
            if not (sd / "metrics.json").exists():
                print(f"AVISO: metrics.json faltando em {sd}", file=sys.stderr)
                continue
            session_dirs.append(sd)

        if not session_dirs:
            print("ERRO: nenhuma sessao valida especificada", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    output = compare_sessions(session_dirs)

    if args.output:
        out_path = Path(args.output).expanduser()
        out_path.write_text(output)
        print(f"Comparacao salva em: {out_path}")
        print(f"Sessoes incluidas: {len(session_dirs)}")
    else:
        print(output)


if __name__ == '__main__':
    main()
