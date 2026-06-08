# Manual do Aplicativo AJR LiDAR

## 1. Finalidade

O AJR LiDAR é um aplicativo desktop para selecionar uma sessão de levantamento LiDAR, executar o processamento e salvar os resultados em uma pasta escolhida pelo usuário.

O fluxo principal utiliza FAST-LIO2 para reconstruir a nuvem de pontos:

```text
Pasta do voo -> arquivo LVX -> ROS bag -> FAST-LIO2 -> PCD -> LAS -> CloudCompare
```

O resultado principal desse fluxo é:

```text
*_fastlio2_map.las
```

O aplicativo também oferece o pipeline Python tradicional para análise, conversão e georreferenciamento de sessões.

## 2. Tela principal

### Pasta de entrada

Permite colar um caminho ou selecionar uma pasta pelo botão **Selecionar**.

A pasta de uma sessão deve conter diretamente um arquivo `.lvx`. Também é possível selecionar uma pasta chamada `input`; nesse caso, o nome da pasta pai será usado como nome da sessão.

Exemplos:

```text
/home/usuario/Downloads/voo_20260604_213246
/home/usuario/Downloads/ajr_lidar/sessoes/voo_20260604_213246/input
```

### Usar FAST-LIO2 Docker e gerar `*_map.las`

Esta opção vem marcada por padrão.

Quando ativada, o aplicativo:

1. procura arquivos `.lvx` na pasta selecionada;
2. escolhe o maior LVX encontrado;
3. rejeita arquivos vazios;
4. limpa mapas antigos da mesma pasta de saída;
5. executa o wrapper `bin/ajr-fastlio2-lvx.sh`;
6. gera os arquivos `*_fastlio2_map.pcd` e `*_fastlio2_map.las`;
7. solicita uma pasta de destino;
8. copia os resultados e logs sem bloquear a interface;
9. abre o LAS salvo no CloudCompare.

O modo FAST-LIO2 processa apenas uma sessão por vez.

### Processar várias sessões

Esta opção pertence ao pipeline Python tradicional. O aplicativo também detecta o modo automaticamente:

- se a pasta selecionada contém `.lvx`, considera uma sessão;
- se ela contém subpastas com `.lvx`, considera várias sessões.

O modo de lote não é aceito quando FAST-LIO2 está ativado.

### Executar Pipeline

Valida a entrada, monta o comando e inicia o processamento em um processo separado. Durante a execução, os campos de configuração são bloqueados e o botão **Parar Pipeline** é habilitado.

### Parar Pipeline

Solicita o encerramento do processo. Se ele não terminar em três segundos, o aplicativo força a parada.

Uma interrupção pode deixar arquivos parciais na pasta interna de saída. Eles não devem ser tratados como resultados finais.

### Limpar Log

Remove da tela todas as mensagens exibidas. Essa ação não apaga resultados nem arquivos de log salvos em disco.

### Log de execução

Exibe em tempo real:

- modo selecionado;
- comando executado;
- saída padrão do processo;
- mensagens de erro;
- arquivos copiados;
- código de saída.

O código de saída `0` indica que o processo terminou com sucesso. Outros códigos indicam falha.

### Indicador de status

O cabeçalho pode apresentar os seguintes estados:

```text
Status: Pronto
Status: Processando...
Status: Finalizado com sucesso
Status: Finalizado com erro
Status: Erro ao iniciar
Status: Copiando resultados...
Status: Resultados salvos
Status: Erro ao salvar
```

## 3. Como processar uma sessão com FAST-LIO2

1. Abra o aplicativo.
2. Clique em **Selecionar**.
3. Escolha uma pasta que contenha um LVX válido.
4. Mantenha marcada a opção **Usar FAST-LIO2 Docker e gerar `*_map.las`**.
5. Clique em **Executar Pipeline**.
6. Acompanhe o processamento no painel de log.
7. Após o sucesso, escolha uma pasta externa para salvar os resultados.
8. Aguarde o status **Resultados salvos**.
9. O aplicativo tentará abrir o LAS no CloudCompare.

## 4. Pastas e resultados

Durante o processamento, os resultados FAST-LIO2 são criados em:

```text
fastlio2_output/<nome_da_sessao>/
```

Na pasta escolhida pelo usuário, o aplicativo cria uma subpasta com o nome da sessão e copia:

```text
<destino>/<nome_da_sessao>/
├── *_fastlio2_map.las
├── *_fastlio2_map.pcd
└── logs/
```

Para o pipeline Python tradicional, a origem interna é:

```text
sessoes/<nome_da_sessao>/
```

O aplicativo copia o LAS considerado mais adequado, arquivos `.csv`, arquivos `.ply`, `relatorio.md` e `metrics.json`, quando existirem.

Não escolha a própria pasta interna `sessoes` como destino. O aplicativo bloqueia esse local para evitar cópias recursivas e uso excessivo de armazenamento.

## 5. Abertura no CloudCompare

Depois de salvar, o aplicativo procura o CloudCompare nesta ordem:

1. comando `cloudcompare` disponível no sistema;
2. instalação Flatpak `org.cloudcompare.CloudCompare`.

Se nenhum deles estiver disponível, os resultados continuam salvos e devem ser abertos manualmente.

No modo FAST-LIO2, o arquivo correto para visualização é:

```text
*_fastlio2_map.las
```

## 6. Validações automáticas

Antes de executar, o aplicativo verifica:

- se uma pasta foi informada;
- se o caminho existe;
- se o caminho é uma pasta;
- se não há outro processo em execução;
- se existe um arquivo `.lvx` no modo FAST-LIO2;
- se o LVX possui tamanho maior que zero;
- se o usuário não selecionou uma pasta de lote no modo FAST-LIO2.

Antes de copiar, verifica:

- se a saída interna realmente existe;
- se o destino não está dentro da pasta interna `sessoes`.

## 7. Requisitos

### Linux

- Python 3.10 ou superior;
- PySide6;
- Docker acessível ao usuário;
- imagem `ajr-fastlio2:noetic`, criada automaticamente quando necessário;
- CloudCompare instalado pelo sistema ou Flatpak.

Comandos de diagnóstico:

```bash
.venv/bin/python -c "import PySide6; print('PySide6 OK')"
docker ps
command -v cloudcompare || flatpak info org.cloudcompare.CloudCompare
```

### Windows

A interface PySide6 pode ser empacotada como executável, mas o fluxo FAST-LIO2 depende de Docker Desktop e WSL2. O código atual ainda chama o wrapper Linux `.sh`; a seleção automática do wrapper `.bat` precisa ser implementada antes da distribuição final para Windows.

## 8. Mensagens comuns

### Nenhum arquivo `.lvx` encontrado

A pasta selecionada não possui um LVX diretamente. Selecione a pasta correta do voo.

### Arquivo `.lvx` vazio ou inválido

O arquivo possui zero bytes. Ele precisa ser substituído por uma captura válida.

### FAST-LIO2 processa uma sessão por vez

Foi selecionada uma pasta que contém várias subpastas de voo. Selecione apenas uma dessas sessões.

### Saída não encontrada para copiar

O processo terminou sem criar a pasta esperada. Consulte o log do aplicativo e `fastlio2_output/<sessao>/logs/`.

### CloudCompare não encontrado

O processamento e o salvamento foram concluídos, mas o visualizador não está instalado ou não está acessível. Abra o LAS salvo manualmente.

## 9. Funções internas do aplicativo

### Execução

- `run_pipeline()`: valida a entrada, escolhe o modo e inicia o comando.
- `pipeline_command()`: monta o comando do pipeline Python.
- `fastlio2_command()`: monta o comando do wrapper FAST-LIO2.
- `read_stdout()` e `read_stderr()`: enviam a saída do processo para o painel de log.
- `process_finished()`: trata o código de saída e inicia o salvamento.
- `process_error()`: trata falhas ao iniciar o processo.
- `stop_pipeline()`: encerra ou força a parada do processo.

### Seleção e validação

- `browse_folder()`: abre o seletor de pastas.
- `detect_batch_mode()`: identifica sessão única ou pasta com várias sessões.
- `find_lvx_file()`: escolhe o maior LVX da pasta.
- `session_name_for()`: determina o nome da sessão, incluindo o caso da pasta `input`.
- `prepare_fastlio_output_dir()`: remove mapas antigos antes de uma nova execução.

### Salvamento

- `prompt_save_results()`: solicita a pasta de destino.
- `start_copy()`: inicia a cópia em uma thread separada para evitar travamentos.
- `CopyWorker.copy_session_results()`: copia apenas os entregáveis relevantes.
- `copy_finished()`: atualiza o estado e abre o resultado salvo.

### CloudCompare

- `cloudcompare_command()`: localiza a instalação nativa ou Flatpak.
- `open_saved_results_in_cloudcompare()`: abre os arquivos LAS usando um processo independente.

### Interface

- `set_running_state()`: habilita e desabilita controles durante o processamento.
- `log()`: adiciona mensagens e mantém a rolagem no final.
- `clear_log()`: limpa somente o painel visual.
- `apply_styles()`: aplica cores e estilos da interface.
