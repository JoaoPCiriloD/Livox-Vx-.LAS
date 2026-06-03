# Livox-Vx-.LAS

Pipeline para processar arquivos Livox `.lvx`, reconstruir trajetória/nuvem com FAST-LIO2 e exportar o resultado para `.las` para abertura no CloudCompare.

O fluxo principal é:

```text
LVX -> ROS bag -> FAST-LIO2 -> PCD -> LAS
```

## O Que Este Projeto Faz

- Converte arquivos `.lvx` do Livox para `rosbag`.
- Executa FAST-LIO2 com configuração para Livox Avia.
- Gera mapa reconstruído em `.pcd`.
- Converte `.pcd` para `.las`.
- Mantém scripts auxiliares para georreferenciamento, inspeção de IMU e comparação de sessões.

## Requisitos

- Docker.
- Python 3.10 ou superior para scripts auxiliares.
- CloudCompare para visualizar `.las`.
- Arquivos de entrada `.lvx`; arquivos `.ubx` são usados pelo pipeline Python de georreferenciamento quando disponíveis.

## Linux

No Linux, o caminho recomendado é Docker, pois o FAST-LIO2 usa ROS Noetic.

```bash
cd /caminho/para/Livox-Vx-.LAS
python3 -m venv .venv
.venv/bin/pip install laspy numpy pyubx2 pyproj
bash fastlio2/scripts/build_fastlio2_docker.sh
```

Para executar todos os voos esperados pelo script:

```bash
bash fastlio2/scripts/run_fastlio2_all_sessions.sh
```

Se o Docker exigir permissões:

```bash
sudo bash fastlio2/scripts/run_fastlio2_all_sessions.sh
```

Saídas esperadas:

```text
fastlio2_output/<sessao>/*_fastlio2_map.pcd
fastlio2_output/<sessao>/*_fastlio2_map.las
```

Para executar um arquivo específico:

```bash
bash fastlio2/scripts/run_fastlio2_docker.sh \
  /caminho/arquivo.lvx \
  fastlio2_output/minha_sessao
```

Para abrir no CloudCompare:

```bash
cloudcompare fastlio2_output/minha_sessao/*_fastlio2_map.las
```

Se estiver usando Flatpak:

```bash
flatpak run org.cloudcompare.CloudCompare fastlio2_output/minha_sessao/*_fastlio2_map.las
```

## Windows

No Windows, use WSL2 com Docker Desktop. Não é recomendado compilar FAST-LIO2/ROS Noetic diretamente no Windows.

1. Instale WSL2.
2. Instale uma distribuição Ubuntu no WSL.
3. Instale Docker Desktop e habilite integração com WSL2.
4. Clone ou copie este projeto para dentro do WSL, por exemplo:

```bash
cd ~
git clone https://github.com/JoaoPCiriloD/Livox-Vx-.LAS.git
cd Livox-Vx-.LAS
```

5. Prepare o ambiente Python e Docker:

```bash
python3 -m venv .venv
.venv/bin/pip install laspy numpy pyubx2 pyproj
bash fastlio2/scripts/build_fastlio2_docker.sh
```

6. Execute:

```bash
bash fastlio2/scripts/run_fastlio2_all_sessions.sh
```

Os arquivos `.las` podem ser abertos no CloudCompare para Windows. Se os resultados estiverem no WSL, acesse pelo Explorer usando:

```text
\\wsl$
```

## macOS

No macOS, o caminho recomendado também é Docker.

1. Instale Docker Desktop para macOS.
2. Instale Python 3.
3. Clone o projeto:

```bash
git clone https://github.com/JoaoPCiriloD/Livox-Vx-.LAS.git
cd Livox-Vx-.LAS
```

4. Prepare dependências Python:

```bash
python3 -m venv .venv
.venv/bin/pip install laspy numpy pyubx2 pyproj
```

5. Construa a imagem:

```bash
bash fastlio2/scripts/build_fastlio2_docker.sh
```

6. Execute um arquivo `.lvx`:

```bash
bash fastlio2/scripts/run_fastlio2_docker.sh \
  /caminho/arquivo.lvx \
  fastlio2_output/minha_sessao
```

Observação: em Macs Apple Silicon, o Docker pode precisar rodar imagem `linux/amd64`, e o processamento tende a ser mais lento.

## Configuração FAST-LIO2

A configuração para Livox Avia fica em:

```text
fastlio2/config/avia_redtech.yaml
```

Parâmetros importantes:

- `lid_topic: /livox/lidar`
- `imu_topic: /livox/imu`
- `lidar_type: 1`
- `scan_line: 6`
- `blind: 0.5`
- `pcd_save_en: true`

## Arquivos Grandes

Este repositório não deve versionar dados brutos ou resultados pesados:

- `.lvx`
- `.ubx`
- `.bag`
- `.pcd`
- `.las`
- `fastlio2_output/`
- `sessoes/`
- `.venv/`

Esses arquivos são ignorados pelo `.gitignore`.

## Scripts Principais

- `fastlio2/scripts/build_fastlio2_docker.sh`: cria a imagem Docker com ROS Noetic, Livox driver e FAST-LIO2.
- `fastlio2/scripts/run_fastlio2_docker.sh`: executa um `.lvx`.
- `fastlio2/scripts/run_fastlio2_all_sessions.sh`: executa os quatro voos configurados.
- `pcd_to_las_redtech.py`: converte PCD do FAST-LIO2 para LAS.
- `redtech_pipeline.py`: pipeline Python original de conversão/georreferenciamento.

## Observações Técnicas

O processamento LIO real é feito pelo FAST-LIO2 dentro do Docker. Ele funde LiDAR e IMU para corrigir distorção de movimento e reconstruir a nuvem registrada. A etapa `.pcd -> .las` preserva coordenadas e intensidade quando disponíveis no PCD.

Para precisão métrica/geográfica final, valide calibração extrínseca, sincronização temporal e georreferenciamento com GNSS/UBX conforme o levantamento.
