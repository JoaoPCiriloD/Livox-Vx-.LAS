# Guia do AJR LiDAR no Windows

Este guia diferencia o pipeline Python tradicional do processamento FAST-LIO2 usado pelo aplicativo.

## Estado atual

- O pipeline Python `ajr.bat` pode rodar diretamente no Windows.
- A interface PySide6 pode rodar diretamente no Windows.
- O FAST-LIO2 depende de ROS Noetic e deve rodar pelo Docker Desktop com WSL2.
- O aplicativo ainda chama o wrapper Linux `.sh`. Antes de distribuir a versao Windows, ele deve selecionar `bin\ajr-fastlio2-lvx.bat` quando estiver no Windows.

Portanto, o aplicativo completo com FAST-LIO2 ainda nao deve ser apresentado como instalavel Windows final.

## Requisitos

1. Windows 10 ou 11.
2. Python 3.10 ou superior.
3. Docker Desktop com integracao WSL2.
4. Ubuntu instalado no WSL2.
5. CloudCompare.

## Preparar o pipeline Python

No PowerShell, dentro do projeto:

```powershell
cd "$env:USERPROFILE\Downloads\ajr_lidar"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para a interface desktop:

```powershell
.\.venv\Scripts\python.exe -m pip install PySide6 pyinstaller
```

## Pipeline Python tradicional

Processar uma sessao:

```powershell
.\ajr.bat "C:\Users\SEU_USUARIO\Downloads\voo_20260604_213246"
```

Processar varias sessoes:

```powershell
.\ajr.bat "C:\Users\SEU_USUARIO\Downloads\Testes" --batch
```

Esse fluxo gera os resultados em:

```text
ajr_lidar\sessoes\<sessao>\
```

Ele nao substitui a reconstrucao do FAST-LIO2. Para avaliar a nuvem reconstruida, o arquivo esperado termina em:

```text
*_fastlio2_map.las
```

## FAST-LIO2 com WSL2

No terminal Ubuntu/WSL:

```bash
cd /mnt/c/Users/SEU_USUARIO/Downloads/ajr_lidar
python3 -m venv .venv-wsl
.venv-wsl/bin/pip install -r requirements.txt
bash fastlio2/scripts/build_fastlio2_docker.sh
```

Para executar um LVX:

```bash
bash bin/ajr-fastlio2-lvx.sh \
  /mnt/c/Users/SEU_USUARIO/Downloads/voo/lidar.lvx \
  fastlio2_output/meu_voo
```

O resultado principal sera:

```text
fastlio2_output/meu_voo/*_fastlio2_map.las
```

Tambem existe o wrapper:

```bat
bin\ajr-fastlio2-lvx.bat "C:\Users\SEU_USUARIO\Downloads\voo\lidar.lvx"
```

## Aplicativo desktop

Depois que a selecao automatica do wrapper por sistema operacional estiver implementada, o comando de abertura no Windows sera:

```powershell
.\.venv\Scripts\python.exe .\ajr_app\manage.py
```

No estado atual, use o app completo no Linux. No Windows, execute o FAST-LIO2 pelo wrapper WSL2 acima.

## Problemas comuns

| Erro | Causa provavel | Solucao |
|---|---|---|
| `No module named PySide6` | Python fora da `.venv` | Use `.\.venv\Scripts\python.exe` |
| Docker nao responde no WSL | Integracao WSL2 desativada | Ative a distribuicao Ubuntu no Docker Desktop |
| Nenhum mapa LAS foi criado | LVX vazio ou falha no FAST-LIO2 | Confirme o tamanho do LVX e consulte os logs |
| CloudCompare nao abre | Executavel fora do PATH | Abra manualmente o `*_fastlio2_map.las` |
