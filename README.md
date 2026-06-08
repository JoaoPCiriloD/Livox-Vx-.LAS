# AJR LiDAR

Aplicativo e pipeline para processamento de dados Livox/LVX com FAST-LIO2, Docker e exportacao LAS para CloudCompare.

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
- PySide6 para o aplicativo desktop.
- CloudCompare para visualizar `.las`.
- Arquivos de entrada `.lvx`; arquivos `.ubx` são usados pelo pipeline Python de georreferenciamento quando disponíveis.

## Estrutura do Projeto

```text
.
├── ajr_app/             # aplicativo desktop PySide6
├── bin/                 # wrappers de execucao Windows/WSL e Linux
├── docs/                # guias, notas e relatorios auxiliares
├── fastlio2/            # Docker, configuracoes e scripts FAST-LIO2
├── outputs/las/         # resultados LAS locais ignorados pelo Git
├── scripts/
│   ├── converters/      # conversores LVX/LAS/PCD/PLY
│   ├── diagnostics/     # inspeção e analise de arquivos LVX
│   ├── georef/          # georreferenciamento GNSS/LIO
│   └── pipeline/        # pipeline principal e comparador
├── ajr.bat
├── ajr-compare.bat
└── requirements.txt
```

## Aplicativo Desktop

Abra o app pela raiz do projeto:

```bash
cd /home/joaop/Downloads/ajr_lidar
source .venv/bin/activate
.venv/bin/python ajr_app/manage.py
```

No app, selecione uma pasta de voo com `.lvx` valido e mantenha marcada a opcao `Usar FAST-LIO2 Docker e gerar *_map.las`. A saida principal esperada e:

```text
fastlio2_output/<sessao>/*_fastlio2_map.las
```

Documentacao do aplicativo:

- `docs/MANUAL_APLICATIVO.md`: manual de uso e referencia das funcoes.
- `docs/APLICATIVO_AJR.md`: instalacao, ambiente e diagnostico.

O fluxo completo do aplicativo esta preparado para Linux. No Windows, a interface exige uma adaptacao para chamar automaticamente o wrapper `.bat`; consulte `docs/GUIA_WINDOWS.md`.

## Execucao Rapida

O executavel principal processa um arquivo `.lvx` e entrega `.pcd` e `.las`:

```bash
bin/ajr-fastlio2-lvx.sh /caminho/arquivo.lvx fastlio2_output/minha_sessao
```

Ele executa:

1. cria/usa `.venv`;
2. instala dependencias Python de `requirements.txt`;
3. constroi a imagem Docker `ajr-fastlio2:noetic` se ela ainda nao existir;
4. converte `.lvx` para `rosbag`;
5. executa FAST-LIO2;
6. converte o mapa `.pcd` para `.las`.

Saidas esperadas:

```text
fastlio2_output/minha_sessao/*_fastlio2_map.pcd
fastlio2_output/minha_sessao/*_fastlio2_map.las
```

## Linux

No Linux, o caminho recomendado é Docker, pois o FAST-LIO2 usa ROS Noetic.

```bash
cd /home/joaop/Downloads/ajr_lidar
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
bash fastlio2/scripts/build_fastlio2_docker.sh
```

Comando recomendado para um arquivo `.lvx`:

```bash
bin/ajr-fastlio2-lvx.sh \
  /home/joao/Downloads/voo_20260603_165720/lidar_2026-06-03T16-57-20Z.lvx \
  fastlio2_output/voo_20260603_165720
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

O FAST-LIO2 no Windows utiliza Docker Desktop com WSL2. O caminho recomendado do projeto é:

```text
C:\Users\SEU_USUARIO\Downloads\ajr_lidar
```

Execução rápida pelo PowerShell:

```powershell
cd "$env:USERPROFILE\Downloads\ajr_lidar"
.\bin\ajr-fastlio2-lvx.bat `
  "C:\Users\SEU_USUARIO\Downloads\voo\lidar.lvx" `
  "C:\Users\SEU_USUARIO\Downloads\resultado_lidar\meu_voo"
```

O guia completo de instalação, conversão de caminhos Windows/WSL, testes e localização dos resultados está em `docs/GUIA_WINDOWS.md`.

## macOS

No macOS, o caminho recomendado também é Docker.

1. Instale Docker Desktop para macOS.
2. Instale Python 3.
3. Clone o projeto:

```bash
# copie ou extraia o projeto
cd ajr_lidar
```

4. Prepare dependências Python:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

5. Execute o fluxo completo:

```bash
bin/ajr-fastlio2-lvx.sh \
  /caminho/arquivo.lvx \
  fastlio2_output/minha_sessao
```

Observação: em Macs Apple Silicon, o Docker pode precisar rodar imagem `linux/amd64`, e o processamento tende a ser mais lento.

## Configuração FAST-LIO2

A configuração para Livox Avia fica em:

```text
fastlio2/config/avia_ajr.yaml
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
- `scripts/converters/lvx_to_las_ajr.py`: converte LVX para LAS local.
- `scripts/converters/pcd_to_las_ajr.py`: converte PCD do FAST-LIO2 para LAS.
- `scripts/converters/las_to_ply_ajr.py`: converte LAS para PLY.
- `scripts/georef/las_geo_ajr.py`: georreferencia LAS local usando UBX.
- `scripts/georef/las_lio_geo_ajr.py`: georreferencia LAS reconstruido usando LVX e UBX.
- `scripts/diagnostics/inspect_lvx_imu.py`: inspeciona amostras IMU do LVX.
- `scripts/pipeline/ajr_pipeline.py`: pipeline Python de conversão/georreferenciamento.
- `scripts/pipeline/ajr_compare.py`: compara sessoes processadas.

## Observações Técnicas

O processamento LIO real é feito pelo FAST-LIO2 dentro do Docker. Ele funde LiDAR e IMU para corrigir distorção de movimento e reconstruir a nuvem registrada. A etapa `.pcd -> .las` preserva coordenadas e intensidade quando disponíveis no PCD.

Para precisão métrica/geográfica final, valide calibração extrínseca, sincronização temporal e georreferenciamento com GNSS/UBX conforme o levantamento.
