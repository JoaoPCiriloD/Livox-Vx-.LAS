# Pipeline AJR com FAST-LIO2

Este documento descreve o caminho correto para substituir a aproximacao inercial simples por um motor LIO real usando FAST-LIO2.

## O que muda

O pipeline Python atual faz:

```text
LVX -> LAS local -> GNSS/UTM
                 -> IMU integrada simples + GNSS/UTM
```

O pipeline FAST-LIO2 passa a ser:

```text
LVX -> rosbag Livox custom msg + IMU
rosbag -> FAST-LIO2 -> mapa registrado PCD + trajetoria
PCD -> LAS final
```

O FAST-LIO2 e o componente que faz a parte pesada: fusao LiDAR-inercial com IKF, deskewing e alinhamento geometrico incremental dos pontos.

## Arquivos adicionados

- `fastlio2/config/avia_ajr.yaml`
- `fastlio2/docker/Dockerfile.noetic`
- `fastlio2/scripts/build_fastlio2_docker.sh`
- `fastlio2/scripts/run_fastlio2_docker.sh`
- `fastlio2/scripts/run_fastlio2_session.sh`
- `scripts/converters/pcd_to_las_ajr.py`
- `fastlio2/scripts/run_pcd_to_las.sh`

## 1. Construir o ambiente FAST-LIO2

```bash
cd /home/joaop/Downloads/ajr_lidar
bash fastlio2/scripts/build_fastlio2_docker.sh
```

Isso cria a imagem:

```text
ajr-fastlio2:noetic
```

Ela contem:

- Ubuntu 20.04 / ROS Noetic;
- `livox_ros_driver`;
- `FAST_LIO`;
- PCL/Eigen/catkin.

## 2. Rodar uma sessao LVX

Exemplo:

```bash
cd /home/joaop/Downloads/ajr_lidar
bash fastlio2/scripts/run_fastlio2_docker.sh \
  /home/joaop/Downloads/drive-download-20260601T172413Z-3-002/voo_20260529_161358/lidar_2026-05-29T16-13-58Z.lvx \
  /home/joaop/Downloads/ajr_lidar/fastlio2_output/voo_20260529_161358
```

Saidas esperadas:

```text
fastlio2_output/voo_20260529_161358/
├── lidar_2026-05-29T16-13-58Z.bag
├── lidar_2026-05-29T16-13-58Z_fastlio2_map.pcd
└── logs/
```

## 3. Converter o mapa FAST-LIO2 para LAS

```bash
cd /home/joaop/Downloads/ajr_lidar
bash fastlio2/scripts/run_pcd_to_las.sh \
  fastlio2_output/voo_20260529_161358/lidar_2026-05-29T16-13-58Z_fastlio2_map.pcd \
  fastlio2_output/voo_20260529_161358/lidar_2026-05-29T16-13-58Z_fastlio2_map.las
```

Depois abra no CloudCompare Flatpak:

```bash
flatpak run org.cloudcompare.CloudCompare \
  /home/joaop/Downloads/ajr_lidar/fastlio2_output/voo_20260529_161358/lidar_2026-05-29T16-13-58Z_fastlio2_map.las
```

## Parametros Avia

O arquivo `fastlio2/config/avia_ajr.yaml` usa:

- `lid_topic: /livox/lidar`
- `imu_topic: /livox/imu`
- `lidar_type: 1` para Livox;
- `scan_line: 6` para Avia;
- `blind: 4`;
- `pcd_save_en: true`;
- `extrinsic_est_en: true`.

`extrinsic_est_en: true` e intencional nesta fase porque ainda nao temos a matriz LiDAR-IMU calibrada do conjunto fisico. Para entrega final, o ideal e substituir por extrinsecos medidos/calibrados.

## Pontos de atencao

1. O FAST-LIO2 precisa de mensagens Livox com timestamp por ponto. Por isso a conversao LVX -> rosbag deve sair em mensagem custom Livox, nao em `sensor_msgs/PointCloud2` sem tempo por ponto.
2. Se o log indicar que nao recebeu `/livox/lidar` ou `/livox/imu`, inspecione o rosbag com:

```bash
rosbag info arquivo.bag
```

3. Se o mapa continuar esfumacado, os proximos itens a ajustar sao:

- extrinsecos LiDAR-IMU;
- eixo/sinal da IMU;
- `time_offset_lidar_to_imu`;
- `acc_cov`, `gyr_cov`, `b_acc_cov`, `b_gyr_cov`;
- qualidade de movimento: trechos muito rapidos ou com pouca geometria reduzem observabilidade.

## Interpretacao

O `_lio_geo.las` atual do pipeline Python deve ser tratado como aproximacao diagnostica.

O arquivo `*_fastlio2_map.las`, gerado a partir do PCD do FAST-LIO2, e a saida correta para avaliar se a reconstrucao de trajetoria resolveu a nuvem esfumacada.
