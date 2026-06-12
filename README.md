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
source .venv-wsl/bin/activate
.venv-wsl/bin/python ajr_app/manage.py
```

No app, selecione uma pasta de voo com `.lvx` valido e mantenha marcada a opcao `Usar FAST-LIO2 Docker e gerar *_map.las`. A saida principal esperada e:

```text
fastlio2_output/<sessao>/*_fastlio2_map.las
```

Documentacao do aplicativo:

- `docs/MANUAL_APLICATIVO.md`: manual de uso e referencia das funcoes.
- `docs/APLICATIVO_AJR.md`: instalacao, ambiente e diagnostico.

No Windows, a interface usa `cmd.exe` e `bin\ajr-fastlio2-lvx.bat` para
encaminhar o processamento ao WSL2/Docker. Use ambientes separados para
Windows e WSL; consulte `docs/GUIA_WINDOWS.md`.

## Execucao Rapida

O executavel principal processa um arquivo `.lvx` e entrega `.pcd` e `.las`:

```bash
bin/ajr-fastlio2-lvx.sh /caminho/arquivo.lvx fastlio2_output/minha_sessao
```

Ele executa:

1. cria/usa `.venv-wsl` no Linux/WSL;
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
python3 -m venv .venv-wsl
.venv-wsl/bin/python -m pip install --upgrade pip
.venv-wsl/bin/python -m pip install -r requirements.txt
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

Use sempre ambientes separados:

```text
.venv-windows -> interface PySide6 executada pelo Windows
.venv-wsl     -> scripts Python executados pelo Ubuntu/WSL
Docker        -> ROS Noetic, Livox ROS Driver e FAST-LIO2
```

Não crie nem reutilize uma pasta chamada `.venv`. Ela pode misturar executáveis
Windows e Linux. O padrão deste projeto é somente `.venv-windows` e
`.venv-wsl`.

Instale no Windows:

- Python 3.10 ou superior;
- WSL2 com Ubuntu;
- Docker Desktop usando o mecanismo WSL2;
- CloudCompare.

Confirme no PowerShell:

```powershell
wsl --list --verbose
wsl --set-default Ubuntu
wsl --list --verbose
wsl docker version
wsl docker ps
```

Use `wsl --set-default Ubuntu` quando o Ubuntu não estiver marcado com `*` na
lista. Se a distribuição possuir outro nome, como `Ubuntu-22.04`, use o nome
exato exibido. O Ubuntu deve aparecer como versão `2`.

Se `docker` não for encontrado dentro do WSL, abra o Docker Desktop e habilite:

```text
Settings > General > Use the WSL 2 based engine
Settings > Resources > WSL Integration > Ubuntu
```

Prepare a interface pelo PowerShell:

```powershell
cd "$env:USERPROFILE\Downloads\ajr_lidar"
py -3 -m venv .venv-windows
.\.venv-windows\Scripts\python.exe -m pip install --upgrade pip
.\.venv-windows\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-windows\Scripts\python.exe -m pip install PySide6 pyinstaller
.\.venv-windows\Scripts\python.exe .\ajr_app\manage.py
```

Prepare o ambiente auxiliar no Ubuntu/WSL:

```bash
cd /mnt/c/Users/SEU_USUARIO/Downloads/ajr_lidar
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv .venv-wsl
.venv-wsl/bin/python -m pip install --upgrade pip
.venv-wsl/bin/python -m pip install -r requirements.txt
sed -i 's/\r$//' fastlio2/scripts/*.sh bin/*.sh
bash -n bin/ajr-fastlio2-lvx.sh
bash -n fastlio2/scripts/run_fastlio2_session.sh
bash fastlio2/scripts/build_fastlio2_docker.sh
```

O aplicativo chama automaticamente o wrapper `.bat`. Para testar o wrapper
sem a interface:

```powershell
cd "$env:USERPROFILE\Downloads\ajr_lidar"
.\bin\ajr-fastlio2-lvx.bat `
  "C:\Users\SEU_USUARIO\Downloads\voo\lidar.lvx" `
  "C:\Users\SEU_USUARIO\Downloads\resultado_lidar\meu_voo"
```

O código de saída `127` significa que algum comando não foi encontrado. Execute:

```powershell
wsl bash -lc "command -v bash; command -v python3; command -v docker"
wsl bash -lc "docker version"
```

Os três comandos precisam retornar caminhos. O wrapper também informa
explicitamente quando `python3`, `docker` ou `.venv-wsl` não estão disponíveis.

O guia completo de ambientes, integração, conversão de caminhos, logs,
salvamento e erros conhecidos está em `docs/GUIA_WINDOWS.md`.

## Visualização no CloudCompare

Abra o arquivo `*_fastlio2_map.las` e siga esta sequência:

1. Selecione a nuvem na **DB Tree**.
2. Em **Properties**, selecione o campo escalar, normalmente **Intensity**.
3. Clique em **Open Color Scales Manager dialog**.
4. Aplique a escala **Blue > Green > Yellow > Red**.
5. Ajuste a faixa exibida em **Properties** para controlar a coloração.
6. Para filtrar pontos, use **Edit > Scalar fields > Filter by Value**.
7. Ative **Display > Shaders > EDL Shaders**.

O procedimento detalhado e os caminhos completos estão em
`docs/MANUAL_APLICATIVO.md` e `docs/GUIA_WINDOWS.md`.

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
python3 -m venv .venv-wsl
.venv-wsl/bin/python -m pip install --upgrade pip
.venv-wsl/bin/python -m pip install -r requirements.txt
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
- `.venv-windows/`
- `.venv-wsl/`

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
