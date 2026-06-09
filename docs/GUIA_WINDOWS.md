# Guia do AJR LiDAR no Windows

Este guia descreve o fluxo integrado do aplicativo PySide6 com FAST-LIO2 no
Windows, usando WSL2 e Docker Desktop.

## 1. Arquitetura

O aplicativo roda nativamente no Windows. O processamento pesado roda no
Ubuntu/WSL2:

```text
PySide6 no Windows
-> cmd.exe
-> bin\ajr-fastlio2-lvx.bat
-> WSL2/Ubuntu
-> Docker Desktop
-> ROS Noetic + FAST-LIO2
-> PCD + LAS em uma pasta do Windows
-> janela para escolher onde salvar
-> CloudCompare
```

Os ambientes têm funções diferentes:

```text
.venv-windows -> interface PySide6 no Windows
.venv-wsl     -> scripts Python auxiliares no Ubuntu/WSL
Docker        -> ROS Noetic, Livox ROS Driver e FAST-LIO2
```

Não reutilize uma mesma `.venv` entre Windows e WSL. Um ambiente Linux contém
`bin/python`; um ambiente Windows contém `Scripts\python.exe`.

## 2. Estrutura esperada

```text
C:\Users\joaop\Livox-Vx-.LAS\
├── .venv-windows\
├── .venv-wsl\
├── ajr_app\
│   └── manage.py
├── bin\
│   ├── ajr-fastlio2-lvx.bat
│   └── ajr-fastlio2-lvx.sh
├── fastlio2\
├── scripts\
├── fastlio2_output\
└── requirements.txt
```

Os nomes podem mudar, mas todos os componentes precisam permanecer na mesma
raiz do projeto.

## 3. Requisitos

- Windows 10 ou 11.
- Python 3.10 ou superior para Windows.
- WSL2 com Ubuntu.
- Docker Desktop com integração WSL habilitada.
- CloudCompare para Windows.
- Arquivo `.lvx` válido e não vazio.
- Espaço livre suficiente para LVX, rosbag, PCD e LAS.

Confirme o WSL2 no PowerShell:

```powershell
wsl --status
wsl --list --verbose
```

O Ubuntu deve aparecer com versão `2`.

Confirme o Docker:

```powershell
wsl docker version
wsl docker ps
```

Se falhar, abra o Docker Desktop e habilite:

```text
Settings > General > Use the WSL 2 based engine
Settings > Resources > WSL Integration > Ubuntu
```

## 4. Ambiente do aplicativo Windows

No PowerShell:

```powershell
cd "C:\Users\joaop\Livox-Vx-.LAS"

py -3 -m venv .venv-windows
.\.venv-windows\Scripts\python.exe -m pip install --upgrade pip
.\.venv-windows\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-windows\Scripts\python.exe -m pip install PySide6 pyinstaller
```

Teste:

```powershell
.\.venv-windows\Scripts\python.exe -c "import PySide6; print('PySide6 OK')"
```

Não execute a interface com uma `.venv` criada no WSL. O erro típico é:

```text
did not find executable at '/usr/bin\python.exe'
```

## 5. Ambiente auxiliar do WSL

No Ubuntu:

```bash
cd /mnt/c/Users/joaop/Livox-Vx-.LAS

sudo apt update
sudo apt install -y python3 python3-venv python3-pip

python3 -m venv .venv-wsl
.venv-wsl/bin/python -m pip install --upgrade pip
.venv-wsl/bin/python -m pip install -r requirements.txt
```

O wrapper Linux deve usar `.venv-wsl/bin/python`, não o ambiente do Windows.

## 6. Construir a imagem Docker

No Ubuntu:

```bash
cd /mnt/c/Users/joaop/Livox-Vx-.LAS
bash fastlio2/scripts/build_fastlio2_docker.sh
```

Confirme:

```bash
docker image inspect ajr-fastlio2:noetic
```

Se aparecer `set: pipefail: invalid option name`, os scripts estão com final de
linha Windows (`CRLF`). Converta para `LF`:

```bash
sed -i 's/\r$//' fastlio2/scripts/*.sh
sed -i 's/\r$//' bin/*.sh
```

Valide um script antes de executar:

```bash
bash -n fastlio2/scripts/run_fastlio2_session.sh
```

Nenhuma saída significa sintaxe válida.

## 7. Integração da interface com Windows

Em `ajr_app\modules\core\tools.py`, `fastlio2_command()` deve selecionar o
wrapper conforme o sistema:

```python
def fastlio2_command(lvx_file, output_dir):
    if sys.platform == "win32":
        return [
            "cmd.exe",
            "/d",
            "/c",
            str(PROJECT_ROOT / "bin" / "ajr-fastlio2-lvx.bat"),
            str(lvx_file),
            str(output_dir),
        ]

    return [
        "bash",
        str(PROJECT_ROOT / "bin" / "ajr-fastlio2-lvx.sh"),
        str(lvx_file),
        str(output_dir),
    ]
```

No log do aplicativo Windows, o comando deve começar com:

```text
cmd.exe /d /c
```

Se começar com `/bin/bash` ou `bash`, o aplicativo ainda está chamando o
wrapper Linux diretamente.

## 8. Wrapper Windows

`bin\ajr-fastlio2-lvx.bat` converte os caminhos Windows para WSL. Ele precisa de
expansão atrasada porque `OUT_WSL` é definido dentro de um bloco:

```bat
@echo off
setlocal EnableDelayedExpansion

if "%~1"=="" goto :help
if "%~1"=="-h" goto :help
if "%~1"=="--help" goto :help

where wsl >nul 2>nul
if errorlevel 1 (
  echo ERRO: WSL2 nao encontrado.
  exit /b 1
)

for /f "delims=" %%I in ('wsl wslpath -a "%~dp0.."') do set "REPO_WSL=%%I"
for /f "delims=" %%I in ('wsl wslpath -a "%~1"') do set "LVX_WSL=%%I"

if "%~2"=="" (
  wsl bash -lc "cd '!REPO_WSL!' && bash bin/ajr-fastlio2-lvx.sh '!LVX_WSL!'"
) else (
  for /f "delims=" %%I in ('wsl wslpath -a "%~2"') do set "OUT_WSL=%%I"
  wsl bash -lc "cd '!REPO_WSL!' && bash bin/ajr-fastlio2-lvx.sh '!LVX_WSL!' '!OUT_WSL!'"
)

exit /b %errorlevel%

:help
echo Uso:
echo   bin\ajr-fastlio2-lvx.bat "C:\caminho\arquivo.lvx" [OUT_DIR]
exit /b 0
```

Sem `EnableDelayedExpansion` e `!OUT_WSL!`, o resultado pode ser criado em:

```text
/mnt/wsl/docker-desktop-bind-mounts/...
```

Nesse caso, o processo termina com código `0`, mas o aplicativo informa:

```text
Saida nao encontrada para copiar
```

## 9. Controle do ROS

`fastlio2/scripts/run_fastlio2_session.sh` deve iniciar somente um `roscore`,
antes da conversão LVX para rosbag, e mantê-lo ativo até o final.

O script também deve:

- esperar `rosparam get /run_id` responder;
- usar o mesmo ROS master na conversão e no FAST-LIO2;
- encerrar `roslaunch`, FAST-LIO2 e `roscore` em `cleanup()`;
- validar se FAST-LIO2 continua ativo antes de tocar o rosbag;
- salvar logs em `<saida>\logs`.

Se dois ROS masters forem iniciados, o log pode mostrar:

```text
RLException: run_id on parameter server does not match declared run_id
[master] killing on exit
Error in XmlRpcClient::writeRequest: write error (Connection refused)
```

Essa execução deve ser interrompida e o controle do `roscore` corrigido.

## 10. Executar o aplicativo

No PowerShell:

```powershell
cd "C:\Users\joaop\Livox-Vx-.LAS"
.\.venv-windows\Scripts\python.exe .\ajr_app\manage.py
```

Não é necessário ativar o ambiente se o caminho completo do Python for usado.

Na interface:

1. Clique em **Selecionar**.
2. Entre na pasta que contém diretamente o `.lvx`.
3. Clique em **Selecionar pasta**.
4. Mantenha marcada a opção FAST-LIO2.
5. Clique em **Executar Pipeline**.
6. Aguarde a conclusão.
7. Escolha uma pasta do Windows quando a janela de salvamento abrir.

O seletor mostra pastas, não arquivos. É normal que `.lvx` e `.ubx` não sejam
exibidos nessa janela.

Para confirmar os arquivos da sessão:

```powershell
Get-ChildItem "C:\caminho\da\sessao" -File |
    Where-Object Extension -in ".lvx", ".ubx"
```

O FAST-LIO2 usa o `.lvx`. O `.ubx` é usado pelo pipeline tradicional de
georreferenciamento quando necessário.

## 11. Etapas esperadas no log

```text
==> Instalando/validando dependencias Python
==> Executando FAST-LIO2
==> Copiando config FAST-LIO2
==> Iniciando roscore
==> Convertendo LVX para rosbag
Rosbag: ...
==> Iniciando FAST-LIO2
==> Tocando rosbag
==> Encerrando FAST-LIO2
PCD FAST-LIO2: ...
==> Convertendo PCD para LAS
Concluido
Codigo da saida: 0
```

`Tocando rosbag` pode permanecer vários minutos sem novas mensagens. Isso não
significa necessariamente travamento.

## 12. Acompanhar o processamento

Ver contêineres ativos:

```powershell
wsl docker ps
wsl docker stats --no-stream
```

CPU ou leitura de disco acima de zero normalmente indicam atividade.

Encontrar a saída mais recente:

```powershell
$saida = Get-ChildItem "C:\Users\joaop\Livox-Vx-.LAS\fastlio2_output" -Directory |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
```

Acompanhar FAST-LIO2:

```powershell
Get-Content "$($saida.FullName)\logs\fastlio2.log" -Tail 30 -Wait
```

Acompanhar rosbag:

```powershell
Get-Content "$($saida.FullName)\logs\rosbag_play.log" -Tail 30 -Wait
```

Pressione `Ctrl+C` para sair do acompanhamento. Isso não interrompe o processo.

## 13. Resultados e salvamento

A saída interna esperada é:

```text
C:\Users\joaop\Livox-Vx-.LAS\fastlio2_output\<sessao>\
├── *_fastlio2_map.pcd
├── *_fastlio2_map.las
└── logs\
```

Após código de saída `0`, o aplicativo deve abrir uma janela para escolher o
destino. Ele cria:

```text
<destino escolhido>\<sessao>\
├── *_fastlio2_map.pcd
├── *_fastlio2_map.las
└── logs\
```

Para localizar qualquer LAS no projeto:

```powershell
Get-ChildItem "C:\Users\joaop\Livox-Vx-.LAS" `
    -Recurse -Filter "*_fastlio2_map.las"
```

## 14. Diagnóstico de erros

| Sintoma ou mensagem | Causa provável | Ação |
|---|---|---|
| `did not find executable at '/usr/bin\python.exe'` | `.venv` Linux usada no Windows | Execute `.venv-windows\Scripts\python.exe` |
| `No module named PySide6` | PySide6 ausente no ambiente Windows | Instale com o Python de `.venv-windows` |
| `/bin/bash: C:\... No such file or directory` | App Windows chamou o `.sh` | Use `cmd.exe /d /c` e o wrapper `.bat` |
| `wsl` não é reconhecido | WSL ausente | Instale WSL2 e Ubuntu |
| Docker não responde | Docker Desktop parado ou sem integração | Ative a integração WSL para Ubuntu |
| `set: pipefail: invalid option name` | Script `.sh` em CRLF | Converta o arquivo para LF |
| `here-document ... wanted 'USAGE'` | Heredoc inválido, indentado ou em CRLF | Use LF, prefira `printf` e valide com `bash -n` |
| `RLException: run_id ... do not match` | Mais de um ROS master | Inicie um único `roscore` antes da conversão |
| `XmlRpcClient ... Connection refused` | `roscore` encerrou durante o processamento | Consulte `roscore.log` |
| Parado em `Tocando rosbag` | Pode estar processando normalmente | Confira `docker stats` e os logs |
| `FAST-LIO2 nao gerou PCD` | FAST-LIO2 falhou ou tópicos são inválidos | Consulte `fastlio2.log` e `rosbag_info.log` |
| `Saida nao encontrada para copiar` | `.bat` perdeu o caminho de saída | Use delayed expansion com `!OUT_WSL!` |
| Código `0`, sem janela de salvamento | Saída criada fora do caminho esperado | Confira `fastlio2_output\<sessao>` |
| CloudCompare não abre | Executável fora do `PATH` | Abra o LAS manualmente ou configure o caminho |
| Nenhum `.lvx` encontrado | Pasta errada ou arquivo em subpasta | Selecione a pasta que contém diretamente o LVX |
| LVX vazio ou inválido | Arquivo com zero bytes | Use uma captura válida |
| Disco cheio | Rosbag, PCD e LAS consomem muito espaço | Libere espaço e remova saídas parciais |

## 15. Logs importantes

```text
logs\lvx_to_rosbag.log
logs\roscore.log
logs\fastlio2.log
logs\rosbag_play.log
logs\rosbag_info.log
logs\normalize_bag.log
```

Ordem recomendada de diagnóstico:

1. `roscore.log`;
2. `lvx_to_rosbag.log`;
3. `rosbag_info.log`;
4. `fastlio2.log`;
5. `rosbag_play.log`.

## 16. Teste mínimo

```powershell
wsl --list --verbose
wsl docker ps
.\.venv-windows\Scripts\python.exe -c "import PySide6; print('PySide6 OK')"
wsl bash -n "/mnt/c/Users/joaop/Livox-Vx-.LAS/fastlio2/scripts/run_fastlio2_session.sh"
```

Teste manual do wrapper:

```powershell
.\bin\ajr-fastlio2-lvx.bat `
  "C:\caminho\arquivo.lvx" `
  "C:\Users\joaop\Livox-Vx-.LAS\fastlio2_output\teste"
```

Considere o ambiente validado quando o LAS aparecer no caminho Windows
informado e a interface abrir a janela para escolher o destino final.
