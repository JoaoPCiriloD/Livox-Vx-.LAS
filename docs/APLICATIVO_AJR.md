# Aplicativo AJR LiDAR

Para o manual completo da interface, fluxo operacional e funcoes internas, consulte `docs/MANUAL_APLICATIVO.md`.

Este guia descreve como executar o aplicativo desktop e o que ele faz.

## Abrir o aplicativo no Linux

A partir da raiz do projeto:

```bash
cd /home/joaop/Downloads/ajr_lidar
source .venv/bin/activate
.venv/bin/python ajr_app/manage.py
```

Se estiver dentro da pasta `ajr_app`, use:

```bash
../.venv/bin/python manage.py
```

Se `python manage.py` mostrar `ModuleNotFoundError: No module named 'PySide6'`, o shell nao esta usando o Python da `.venv`. Confira com:

```bash
which python
python -c "import sys; print(sys.executable)"
```

O caminho correto deve ser:

```text
/home/joaop/Downloads/ajr_lidar/.venv/bin/python
```

## Dependencias do app

```bash
cd /home/joaop/Downloads/ajr_lidar
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install PySide6 pyinstaller
```

## Fluxo principal do app

Por padrao, o aplicativo usa FAST-LIO2 com Docker:

```text
LVX -> ROS bag -> FAST-LIO2 Docker -> PCD -> *_fastlio2_map.las -> CloudCompare
```

O arquivo esperado para visualizacao e entrega tecnica e:

```text
fastlio2_output/<sessao>/*_fastlio2_map.las
```

## Como selecionar a pasta

Selecione uma pasta de voo que contenha um `.lvx` valido, por exemplo:

```text
/home/joaop/Downloads/voo_20260604_213415
```

Tambem e aceito selecionar a subpasta `input` de uma sessao ja organizada:

```text
/home/joaop/Downloads/ajr_lidar/sessoes/voo_20260604_213415/input
```

Nesse caso, o app usa o nome da pasta pai (`voo_20260604_213415`) para criar a saida, evitando salvar como `fastlio2_output/input`.

Nao processe arquivos `.lvx` com 0 bytes. O app bloqueia esse caso e mostra:

```text
Erro: arquivo .lvx vazio ou invalido
```

## Salvamento e CloudCompare

Ao finalizar com sucesso, o app pede uma pasta para salvar os resultados. Ele copia apenas os entregaveis do FAST-LIO2:

```text
*_fastlio2_map.las
*_fastlio2_map.pcd
logs/
```

Depois abre automaticamente o `*_fastlio2_map.las` no CloudCompare.

Nao escolha a pasta interna do projeto como destino de salvamento:

```text
/home/joaop/Downloads/ajr_lidar/sessoes
```

Isso evita copias recursivas e consumo excessivo de disco.

## Docker

O app nao roda FAST-LIO2 diretamente no Python. Ele chama:

```text
bin/ajr-fastlio2-lvx.sh
```

Esse script usa Docker local com a imagem:

```text
ajr-fastlio2:noetic
```

Verifique se o Docker esta acessivel:

```bash
docker ps
```

Se a imagem ainda nao existir, o wrapper tenta construir automaticamente.

## Windows

No Windows, o app visual pode funcionar com PySide6, mas o FAST-LIO2 precisa de Docker Desktop com WSL2. O fluxo recomendado e:

```text
App Windows -> bin/ajr-fastlio2-lvx.bat -> WSL -> Docker -> FAST-LIO2
```

O app deve chamar o `.bat` no Windows e o `.sh` no Linux/macOS.


## Estado do suporte Windows

A selecao automatica do wrapper por sistema operacional ainda precisa ser implementada. Atualmente, o fluxo completo do app esta preparado para Linux. Consulte `docs/GUIA_WINDOWS.md`.

## Diagnostico rapido

Verifique o ambiente antes de abrir o app:

```bash
.venv/bin/python -c "import PySide6; print('PySide6 OK')"
docker ps
command -v cloudcompare || flatpak info org.cloudcompare.CloudCompare
```

Se o processamento terminar, mas o mapa nao for criado, confira:

```text
fastlio2_output/<sessao>/logs/
```

O arquivo LVX selecionado deve existir e ter tamanho maior que zero.
