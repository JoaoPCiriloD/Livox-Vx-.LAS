# Processamento conforme nota tecnica do cliente

**Data:** 2026-06-02  
**Base:** NOTA_TECNICA_CLIENTE_2026-05-31.pdf, GUIA_WINDOWS.pdf e execucao Linux local

## 1. Objetivo

Processar os dados LiDAR/GNSS recebidos, verificar a diferenca entre a visualizacao/exportacao do Livox Viewer e o processamento tecnico do pipeline, e avaliar a reconstrucao de trajetoria considerando odometria LiDAR-inercial.

## 2. Arquivo exportado pelo Livox Viewer

Arquivo identificado:

`/home/joaop/Downloads/teste_1.las`

Metricas:

- Pontos: 96.384
- LAS Point Format: 2
- GPS time: ausente
- Bounds:
  - X: 0 a 78.010
  - Y: -49.324 a 43.189
  - Z: -51.174 a 61.667

Conclusao:

O `teste_1.las` e uma exportacao visual/local do Livox Viewer. Ele serve para confirmar que a captura ocorreu e para inspecao visual basica, mas nao serve como entrada principal para reconstrucao de trajetoria, porque nao contem `gps_time` por ponto. Sem `gps_time`, nao ha como sincronizar cada ponto com GNSS/IMU.

## 3. Dados brutos usados para reconstrucao

As entradas tecnicamente validas para reconstrucao sao os arquivos `.lvx`, porque preservam:

- timestamps dos pacotes LiDAR;
- pacotes IMU embutidos;
- estrutura temporal da varredura;
- sincronizacao necessaria com GNSS/UBX.

Foram processadas 4 sessoes:

| Sessao | Pontos | IMU | timestamp_type=3 | Status |
|---|---:|---:|---:|---|
| voo_20260529_125507 | 15.013.896 | 201.3 Hz | 100.0% | OK |
| voo_20260529_161358 | 13.310.717 | 204.4 Hz | 100.0% | OK |
| voo_20260529_161524 | 11.773.955 | 204.2 Hz | 100.0% | OK |
| voo_20260529_161652 | 12.806.924 | 204.3 Hz | 100.0% | OK |

## 4. Saidas geradas

Para cada sessao, foram geradas duas saidas:

- `_geo.las`: conversao LVX -> LAS e georreferenciamento por translacao GNSS/UTM.
- `_lio_geo.las`: reconstrucao inercial aplicada, usando orientacao estimada pela IMU do LVX antes da translacao GNSS/UTM.

Tambem foi gerado um CSV de trajetoria LIO por sessao:

- `trajetoria_lio_*.csv`

## 5. Avaliacao da reconstrucao LIO atual

A etapa LIO implementada no pipeline considera:

1. extracao da IMU do LVX;
2. estimativa de bias inicial do giroscopio;
3. integracao do gyro para roll/pitch/yaw;
4. interpolacao da orientacao por timestamp;
5. rotacao dos pontos LiDAR;
6. translacao GNSS/UTM.

Comparacao de dimensoes GNSS vs LIO:

| Sessao | GNSS Z range | LIO Z range | Leitura tecnica |
|---|---:|---:|---|
| voo_20260529_125507 | 191.5 m | 221.5 m | LIO altera orientacao, mas ainda ha distorcao |
| voo_20260529_161358 | 188.3 m | 195.6 m | Alteracao moderada |
| voo_20260529_161524 | 329.7 m | 240.7 m | LIO reduz faixa Z, mas nao estabiliza completamente |
| voo_20260529_161652 | 148.2 m | 240.6 m | LIO aumenta faixa Z, indicando sensibilidade de eixo/bias |

Conclusao tecnica:

A reconstrucao inercial atual ja considera IMU, mas ainda nao equivale a uma reconstrucao LiDAR-inercial completa como FAST-LIO ou LIO-SAM. A imagem observada no CloudCompare, com nuvem em formato de coluna/fita e varreduras empilhadas, indica que ainda existe erro de pose/orientacao ao longo do voo.

Isso e coerente com a nota tecnica: a nuvem final pronta para analise exige reconstrucao de trajetoria por odometria LiDAR-inercial com correcao geometrica entre varreduras, nao apenas integracao de IMU.

## 6. Proxima etapa recomendada

Para chegar ao resultado esperado na nota do cliente, o proximo passo deve ser um modulo LIO/SLAM completo:

- sincronizacao LiDAR/IMU/GNSS;
- calibracao extrinseca LiDAR-IMU;
- ajuste de eixos IMU/LiDAR;
- scan matching/ICP entre varreduras;
- correcao de deriva por EKF ou otimizacao em grafo;
- frameworks recomendados: FAST-LIO ou LIO-SAM.

Antes de integrar FAST-LIO/LIO-SAM, recomenda-se testar remapeamentos de eixo IMU/LiDAR e sinais de gyro no modulo atual, porque a distorcao visual sugere possivel desalinhamento entre o referencial da IMU e o referencial dos pontos LiDAR.

## 7. Conclusao

O equipamento captura dados validos: os LVX contem pontos, timestamps GPS/UTC e IMU a aproximadamente 200 Hz. O pipeline Linux processou os dados, gerou nuvens GNSS e nuvens com orientacao inercial aplicada.

O arquivo `teste_1.las` do Livox Viewer deve ser tratado como referencia visual, nao como base de reconstrucao. A base correta e o `.lvx`.

A questao da reconstrucao ainda nao esta finalizada para entrega de nuvem analitica: a etapa atual e uma reconstrucao inercial inicial. Para atender plenamente a nota do cliente, e necessario evoluir para LIO completo com scan matching/otimizacao.
