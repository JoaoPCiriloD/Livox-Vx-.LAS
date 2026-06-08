# Guia Completo do AJR LiDAR no Windows

Este guia explica como organizar o projeto, preparar o Windows, executar o pipeline FAST-LIO2 pelo WSL2 e localizar os resultados.

## 1. Como o processamento funciona no Windows

O aplicativo possui interface Windows, mas o FAST-LIO2 depende de ROS Noetic e ferramentas Linux. Por isso, o processamento usa esta arquitetura:

```text
Windows -> aplicativo ou arquivo .bat -> WSL2/Ubuntu -> Docker -> FAST-LIO2 -> LAS -> CloudCompare Windows
```

O Docker utilizado é local: ele roda no computador do cliente por meio do Docker Desktop.

## 2. Estado atual do aplicativo

Atualmente:

- `ajr.bat` executa o pipeline Python diretamente no Windows;
- `bin\ajr-fastlio2-lvx.bat` executa FAST-LIO2 pelo WSL2;
- a interface PySide6 pode abrir no Windows;
- a interface ainda precisa ser adaptada para escolher automaticamente o `.bat` no Windows, pois hoje chama o wrapper Linux `.sh`.

Enquanto essa adaptação não for implementada, teste o FAST-LIO2 no Windows usando `bin\ajr-fastlio2-lvx.bat`.

## 3. Caminho recomendado do projeto

Extraia ou copie o projeto para:

```text
C:\Users\SEU_USUARIO\Downloads\ajr_lidar
```

Exemplo para o usuário João:

```text
C:\Users\Joao\Downloads\ajr_lidar
```

A estrutura mínima esperada é:

```text
C:\Users\SEU_USUARIO\Downloads\ajr_lidar\
├── ajr_app\
├── bin\
│   ├── ajr-fastlio2-lvx.bat
│   └── ajr-fastlio2-lvx.sh
├── fastlio2\
├── scripts\
├── requirements.txt
└── README.md
```

Evite nomes diferentes, como `ajrd_app`, e não coloque o projeto dentro de outra pasta com o mesmo nome.

## 4. Instalar os requisitos

### 4.1 WSL2 e Ubuntu

Abra o PowerShell como administrador e execute:

```powershell
wsl --install -d Ubuntu
```

Reinicie o computador quando solicitado. Depois abra o Ubuntu pelo menu Iniciar e conclua a criação do usuário Linux.

Confirme no PowerShell:

```powershell
wsl --status
wsl --list --verbose
```

A distribuição Ubuntu deve aparecer usando a versão `2`.

Caso apareça como versão `1`:

```powershell
wsl --set-version Ubuntu 2
```

### 4.2 Docker Desktop

1. Instale o Docker Desktop para Windows.
2. Abra **Settings > General**.
3. Ative **Use the WSL 2 based engine**.
4. Abra **Settings > Resources > WSL Integration**.
5. Ative a integração para a distribuição Ubuntu.
6. Reinicie o Docker Desktop.

No terminal Ubuntu, confirme:

```bash
docker version
docker ps
```

### 4.3 Python para Windows

Instale Python 3.10 ou superior e marque **Add Python to PATH** durante a instalação.

No PowerShell:

```powershell
python --version
```

### 4.4 CloudCompare

Instale a versão Windows do CloudCompare. Ele será usado para abrir o arquivo final:

```text
*_fastlio2_map.las
```

## 5. Preparar o ambiente Python do Windows

Abra o PowerShell e entre na raiz do projeto:

```powershell
cd "$env:USERPROFILE\Downloads\ajr_lidar"
```

Crie a `.venv`:

```powershell
python -m venv .venv
```

Instale as dependências usando diretamente o Python dessa `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install PySide6 pyinstaller
```

Teste o PySide6:

```powershell
.\.venv\Scripts\python.exe -c "import PySide6; print('PySide6 OK')"
```

Usar o caminho completo da `.venv` evita o erro:

```text
ModuleNotFoundError: No module named 'PySide6'
```

## 6. Entender os caminhos Windows e WSL

O mesmo diretório possui caminhos diferentes em cada ambiente:

```text
Windows: C:\Users\Joao\Downloads\ajr_lidar
WSL:     /mnt/c/Users/Joao/Downloads/ajr_lidar
```

Outro exemplo:

```text
Windows: C:\Users\Joao\Downloads\voo_20260604_213246\lidar.lvx
WSL:     /mnt/c/Users/Joao/Downloads/voo_20260604_213246/lidar.lvx
```

Para converter manualmente um caminho no WSL:

```bash
wslpath 'C:\Users\Joao\Downloads\voo\lidar.lvx'
```

O wrapper `.bat` já faz essa conversão automaticamente.

## 7. Preparar o ambiente dentro do WSL

Abra o Ubuntu e acesse o projeto:

```bash
cd /mnt/c/Users/SEU_USUARIO/Downloads/ajr_lidar
```

Exemplo:

```bash
cd /mnt/c/Users/Joao/Downloads/ajr_lidar
```

Instale os componentes básicos, caso ainda não existam:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

Crie um ambiente separado para o WSL:

```bash
python3 -m venv .venv-wsl
.venv-wsl/bin/python -m pip install --upgrade pip
.venv-wsl/bin/python -m pip install -r requirements.txt
```

Construa a imagem FAST-LIO2:

```bash
bash fastlio2/scripts/build_fastlio2_docker.sh
```

A imagem esperada é:

```text
ajr-fastlio2:noetic
```

Confirme:

```bash
docker image inspect ajr-fastlio2:noetic
```

## 8. Executar pelo PowerShell

Este é o caminho mais simples para testar no Windows.

Entre na raiz do projeto:

```powershell
cd "$env:USERPROFILE\Downloads\ajr_lidar"
```

Execute informando o arquivo LVX:

```powershell
.\bin\ajr-fastlio2-lvx.bat `
  "C:\Users\SEU_USUARIO\Downloads\voo_20260604_213246\lidar.lvx"
```

Para escolher a pasta de saída:

```powershell
.\bin\ajr-fastlio2-lvx.bat `
  "C:\Users\SEU_USUARIO\Downloads\voo_20260604_213246\lidar.lvx" `
  "C:\Users\SEU_USUARIO\Downloads\resultado_lidar\voo_20260604_213246"
```

Em uma única linha:

```powershell
.\bin\ajr-fastlio2-lvx.bat "C:\Users\SEU_USUARIO\Downloads\voo\lidar.lvx" "C:\Users\SEU_USUARIO\Downloads\resultado_lidar\meu_voo"
```

Sempre coloque caminhos entre aspas, principalmente quando houver espaços.

## 9. Executar diretamente pelo Ubuntu/WSL

Entre no projeto:

```bash
cd /mnt/c/Users/SEU_USUARIO/Downloads/ajr_lidar
```

Execute:

```bash
bash bin/ajr-fastlio2-lvx.sh \
  /mnt/c/Users/SEU_USUARIO/Downloads/voo_20260604_213246/lidar.lvx \
  /mnt/c/Users/SEU_USUARIO/Downloads/resultado_lidar/voo_20260604_213246
```

O fluxo executado será:

```text
LVX -> ROS bag -> FAST-LIO2 -> PCD -> LAS
```

## 10. Abrir a interface no Windows

No estado atual, a interface pode ser aberta para testar o layout e o pipeline Python:

```powershell
cd "$env:USERPROFILE\Downloads\ajr_lidar"
.\.venv\Scripts\python.exe .\ajr_app\manage.py
```

Não use apenas `python manage.py` sem confirmar o ambiente, pois isso pode chamar outro Python instalado no Windows.

O botão FAST-LIO2 do app só estará pronto para uso no Windows depois que o código selecionar `bin\ajr-fastlio2-lvx.bat` nesse sistema.

## 11. Pipeline Python tradicional

Para processar uma sessão sem FAST-LIO2:

```powershell
cd "$env:USERPROFILE\Downloads\ajr_lidar"
.\ajr.bat "C:\Users\SEU_USUARIO\Downloads\voo_20260604_213246"
```

Para várias sessões:

```powershell
.\ajr.bat "C:\Users\SEU_USUARIO\Downloads\Testes" --batch
```

Os resultados ficam em:

```text
C:\Users\SEU_USUARIO\Downloads\ajr_lidar\sessoes\<nome_da_sessao>
```

Esse pipeline não substitui o mapa reconstruído pelo FAST-LIO2.

## 12. Localizar os resultados

Quando uma pasta de saída Windows for informada ao `.bat`, procure:

```text
C:\Users\SEU_USUARIO\Downloads\resultado_lidar\<sessao>\
├── *_fastlio2_map.pcd
├── *_fastlio2_map.las
└── logs\
```

O arquivo recomendado para abrir no CloudCompare é:

```text
*_fastlio2_map.las
```

Se os resultados forem salvos no sistema de arquivos do Ubuntu, abra o Explorador de Arquivos e digite:

```text
\\wsl$\Ubuntu
```

É preferível salvar resultados em `/mnt/c/...`, pois eles ficam diretamente acessíveis pelo Windows.

## 13. Teste mínimo antes de gerar o executável

Execute na ordem:

```powershell
wsl --list --verbose
wsl docker ps
.\.venv\Scripts\python.exe -c "import PySide6; print('PySide6 OK')"
.\bin\ajr-fastlio2-lvx.bat "C:\caminho\para\arquivo_valido.lvx" "C:\caminho\para\resultado"
```

Considere o ambiente aprovado quando:

1. o WSL2 estiver ativo;
2. o Docker responder dentro do WSL;
3. o PySide6 importar sem erro;
4. o wrapper gerar `*_fastlio2_map.las`;
5. o LAS abrir corretamente no CloudCompare para Windows.

## 14. Problemas comuns

| Erro | Causa provável | Solução |
|---|---|---|
| `No module named PySide6` | Python fora da `.venv` | Use `.\.venv\Scripts\python.exe` |
| `wsl` não é reconhecido | WSL2 não instalado | Execute `wsl --install -d Ubuntu` como administrador |
| Docker não responde no Ubuntu | Integração WSL desativada | Ative Ubuntu em Docker Desktop > WSL Integration |
| `bash` não é reconhecido pelo app | App ainda chamou o wrapper Linux no Windows | Use `bin\ajr-fastlio2-lvx.bat` manualmente |
| Arquivo LVX não encontrado | Caminho incorreto ou sem aspas | Use o caminho completo entre aspas |
| LVX vazio ou inválido | Arquivo com zero bytes | Use uma captura LVX válida |
| Nenhum mapa LAS foi criado | Falha no FAST-LIO2 | Consulte a pasta `logs` da saída |
| CloudCompare não abre | Instalação ausente ou fora do PATH | Abra manualmente o `*_fastlio2_map.las` |
| Acesso negado pelo Docker | Docker Desktop parado | Abra o Docker Desktop e aguarde inicializar |

## 15. Próximo passo para o executável

Antes de gerar o `.exe`, o aplicativo precisa:

1. detectar `sys.platform == "win32"`;
2. chamar `bin\ajr-fastlio2-lvx.bat` no Windows;
3. localizar o CloudCompare instalado no Windows;
4. armazenar saídas em caminhos graváveis fora da pasta do executável;
5. incluir a logo e os scripts necessários no pacote PyInstaller;
6. ser testado em uma instalação limpa do Windows.
