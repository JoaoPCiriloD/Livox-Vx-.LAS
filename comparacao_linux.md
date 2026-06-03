# Comparacao de Sessoes RedTech

**Gerado em:** 2026-06-02 17:45:48
**Sessoes comparadas:** 4

## Sessoes Incluidas

| Sessao | Inicio LVX (UTC) | Pass | Warn | Fail | Status |
|---|---|:---:|:---:|:---:|:---:|
| voo_20260529_125507 | 2026-05-29 13:16:49 UTC | 11/13 | 2 | 0 | WARN |
| voo_20260529_161358 | 2026-05-29 16:59:16 UTC | 11/13 | 2 | 0 | WARN |
| voo_20260529_161524 | 2026-05-29 17:00:43 UTC | 11/13 | 2 | 0 | WARN |
| voo_20260529_161652 | 2026-05-29 17:02:09 UTC | 11/13 | 2 | 0 | WARN |

## GNSS (gnss.ubx)

| Sessao | NAV-PVT | Fix 3D | RAWX | Sats | pDOP | hAcc | Duracao |
|---|---:|---:|---:|---:|---:|---:|---:|
| voo_20260529_125507 | 419 | 419 | 0 | 26.0 | 1.03 | 614mm | 83s |
| voo_20260529_161358 | 418 | 418 | 0 | 29.0 | 1.09 | 499mm | 84s |
| voo_20260529_161524 | 421 | 421 | 0 | 29.0 | 1.10 | 544mm | 84s |
| voo_20260529_161652 | 419 | 419 | 0 | 29.0 | 1.10 | 579mm | 84s |

## LiDAR (lidar.lvx)

| Sessao | Tamanho | Frames | Packages | ts=3 | Duracao | IMU | Modo |
|---|---:|---:|---:|---:|---:|---:|:---:|
| voo_20260529_125507 | 410.7MB | 1200 | 313229 | 100.0% | 61.1s | 201.3Hz | Dual |
| voo_20260529_161358 | 410.7MB | 1200 | 313165 | 100.0% | 60.1s | 204.4Hz | Dual |
| voo_20260529_161524 | 410.7MB | 1200 | 313154 | 100.0% | 60.1s | 204.2Hz | Dual |
| voo_20260529_161652 | 410.7MB | 1200 | 313203 | 100.0% | 60.1s | 204.3Hz | Dual |

## Cobertura Temporal (UBX vs LVX)

| Sessao | Margem inicio | Margem fim | Cobertura |
|---|---:|---:|:---:|
| voo_20260529_125507 | +12.4s | +9.5s | OK |
| voo_20260529_161358 | +14.0s | +9.9s | OK |
| voo_20260529_161524 | +14.0s | +9.9s | OK |
| voo_20260529_161652 | +13.8s | +10.1s | OK |

## Posicao (Centro da nuvem)

| Sessao | Lat | Lon | Z range | Pontos validos |
|---|---:|---:|---:|---:|
| voo_20260529_125507 | -27.617875 | -48.655516 | -48.8 a 142.6m | 15013896 |
| voo_20260529_161358 | -27.477322 | -48.699662 | -22.8 a 165.5m | 13310717 |
| voo_20260529_161524 | -27.477042 | -48.700190 | -99.0 a 230.7m | 11773955 |
| voo_20260529_161652 | -27.478482 | -48.702404 | -5.5 a 142.8m | 12806924 |

## Links Google Maps

- **voo_20260529_125507:** https://www.google.com/maps?q=-27.617875373795858,-48.65551648057496
- **voo_20260529_161358:** https://www.google.com/maps?q=-27.477321822853767,-48.69966237916175
- **voo_20260529_161524:** https://www.google.com/maps?q=-27.477041683521524,-48.7001897524604
- **voo_20260529_161652:** https://www.google.com/maps?q=-27.4784823234493,-48.70240417202976

## Reconstrucao de Trajetoria LiDAR-Inercial (LIO)

O pipeline agora gera tambem arquivos `_lio_geo.las`, aplicando orientacao estimada pela IMU do LVX antes da translacao GNSS/UTM. Esta etapa considera odometria inercial do LiDAR para reconstruir a trajetoria de orientacao do sensor. Um refinamento LIO completo com scan matching/ICP ainda pode ser feito com LIO-SAM ou FAST-LIO.

| Sessao | LIO aplicada | Entradas prontas | IMU | ts=3 | Proxima etapa |
|---|:---:|:---:|---:|---:|---|
| voo_20260529_125507 | Sim | Sim | 201.3Hz | 100.0% | LIO-SAM / FAST-LIO |
| voo_20260529_161358 | Sim | Sim | 204.4Hz | 100.0% | LIO-SAM / FAST-LIO |
| voo_20260529_161524 | Sim | Sim | 204.2Hz | 100.0% | LIO-SAM / FAST-LIO |
| voo_20260529_161652 | Sim | Sim | 204.3Hz | 100.0% | LIO-SAM / FAST-LIO |

Etapas tecnicas: sincronizacao temporal LiDAR/IMU, calibracao extrinseca, integracao inercial para previsao de pose, scan matching/ICP entre varreduras e correcao por EKF ou otimizacao em grafo de fatores.

## Diferencas entre Sessoes Consecutivas

Distancia (metros) entre centros das nuvens georreferenciadas.

| Sessao A | Sessao B | Distancia |
|---|---|---:|
| voo_20260529_125507 | voo_20260529_161358 | 16173.9m |
| voo_20260529_161358 | voo_20260529_161524 | 60.7m |
| voo_20260529_161524 | voo_20260529_161652 | 270.9m |

---

*Gerado por redtech_compare.py v1.0*