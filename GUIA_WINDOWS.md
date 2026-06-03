# Guia de Setup — RedTech LiDAR Pipeline (Windows)

**Para:** João (execução técnica)
**Objetivo:** rodar o mesmo pipeline do Mac no Windows
**Versão:** 1.1 — 29/05/2026

---

> ✅ **STATUS DE VALIDAÇÃO (atualizado 29/05/2026)**
>
> O Windows **já foi validado** — o pipeline rodou, leu UBX/LVX/str2str,
> gerou relatórios. O único erro na primeira tentativa foi um **conversor
> desatualizado** no pacote anterior. Este pacote corrige isso: o conversor
> agora é `lvx_to_las_redtech.py` (versão chunked, sem o bug de Dual Return).
>
> **IMPORTANTE — se você já tinha um pacote antigo:**
> APAGUE qualquer `lvx_to_las_redtech_v2.py` ou `lvx_to_las_redtech_v3.py`
> da pasta `LIDAR_tests` antes de copiar os novos arquivos. Deve sobrar
> apenas `lvx_to_las_redtech.py`.

---

## O que você vai instalar

| Item | Para quê |
|------|----------|
| Python 3 | Roda os scripts |
| Bibliotecas (laspy, numpy, pyubx2, pyproj) | Processamento LiDAR/GNSS |
| CloudCompare | Visualizar a nuvem de pontos |
| Scripts RedTech (.py) | O pipeline em si |
| Arquivos .bat | Atalhos para rodar fácil |

---

## PASSO 1 — Instalar Python

1. Vá em https://www.python.org/downloads/
2. Baixe a versão mais recente do Python 3
3. Rode o instalador
4. **CRÍTICO:** na primeira tela, marque a caixa **"Add Python to PATH"** (fica embaixo)
5. Clique "Install Now"

Para confirmar, abra o **PowerShell** (tecla Windows → digite "PowerShell") e rode:

```powershell
python --version
```

Deve aparecer algo como `Python 3.12.x`. Se aparecer erro, o Python não foi adicionado ao PATH — reinstale marcando a caixa.

---

## PASSO 2 — Criar a estrutura de pastas

No PowerShell:

```powershell
mkdir "$env:USERPROFILE\Downloads\LIDAR_tests\sessoes"
```

Isso cria:
```
C:\Users\SEU_USUARIO\Downloads\LIDAR_tests\
└── sessoes\
```

---

## PASSO 3 — Copiar os arquivos

Copie para dentro de `C:\Users\SEU_USUARIO\Downloads\LIDAR_tests\`:

**Os 5 scripts Python:**
- `redtech_pipeline.py`
- `redtech_compare.py`
- `lvx_to_las_redtech.py`
- `las_geo_redtech.py`
- `analyze_lvx_v2.5.py`

**Os arquivos .bat:**
- `redtech.bat`
- `redtech-compare.bat`
- `SETUP.bat`

A pasta deve ficar assim:
```
LIDAR_tests\
├── redtech_pipeline.py
├── redtech_compare.py
├── lvx_to_las_redtech.py
├── las_geo_redtech.py
├── analyze_lvx_v2.5.py
├── redtech.bat
├── redtech-compare.bat
├── SETUP.bat
└── sessoes\
```

---

## PASSO 4 — Rodar o SETUP.bat

Na pasta `LIDAR_tests`, **dê duplo-clique em `SETUP.bat`**.

Ele vai:
1. Verificar Python
2. Instalar as bibliotecas (laspy, numpy, pyubx2, pyproj)
3. Validar que tudo importa
4. Confirmar a estrutura de pastas

**Espere terminar.** A primeira instalação das bibliotecas pode levar alguns minutos.

Se der erro, leia a mensagem — geralmente é Python não estar no PATH (volte ao Passo 1).

---

## PASSO 5 — Instalar CloudCompare

1. Vá em https://www.danielgm.net/cc/release/
2. Baixe a versão Windows (64-bit) mais recente
3. Instale normalmente (next, next, finish)

O pipeline vai procurar o CloudCompare automaticamente nos locais padrão. Se instalar em local diferente, o pipeline avisa e você abre manualmente.

---

## PASSO 6 — Testar

Abra o PowerShell e vá para a pasta:

```powershell
cd "$env:USERPROFILE\Downloads\LIDAR_tests"
```

Teste o help:

```powershell
.\redtech.bat --help
```

Deve aparecer a tela de ajuda do pipeline. **Se aparecer, está funcionando.**

---

## USO DIÁRIO

### Quando receber uma pasta de testes

Supondo que você recebeu `C:\Users\Joao\Downloads\Teste 2` com várias subpastas `voo_*`:

```powershell
cd "$env:USERPROFILE\Downloads\LIDAR_tests"
.\redtech.bat "C:\Users\Joao\Downloads\Teste 2" --batch
```

Isso processa **todas** as subpastas de uma vez.

### Comparar todas as sessões

```powershell
.\redtech-compare.bat --all
```

### Salvar comparação em arquivo

```powershell
.\redtech-compare.bat --all --output "$env:USERPROFILE\Downloads\comparacao.md"
```

### Processar UMA pasta só

```powershell
.\redtech.bat "C:\Users\Joao\Downloads\Teste 2\voo_20260527_142555"
```

### Casos especiais (outras regiões)

```powershell
REM Acre (UTM 19 sul)
.\redtech.bat "C:\caminho\Teste" --batch --utm-zone 19

REM Roraima (UTM 20 NORTE - acima do equador)
.\redtech.bat "C:\caminho\Teste" --batch --utm-zone 20 --hemisphere north
```

---

## RODAR DE QUALQUER PASTA (opcional)

Por padrão você precisa estar dentro de `LIDAR_tests` ou digitar `.\redtech.bat`.

Para rodar `redtech` de qualquer lugar (igual no Mac), veja o arquivo
**`ADICIONAR_AO_PATH.txt`**.

---

## DIFERENÇAS Mac vs Windows (referência)

| Tarefa | Mac | Windows |
|--------|-----|---------|
| Comando Python | `python3` | `python` |
| Rodar pipeline | `redtech "pasta" --batch` | `.\redtech.bat "pasta" --batch` |
| Separador de caminho | `/` | `\` (mas `/` também funciona em Python) |
| Pasta home | `~/` | `%USERPROFILE%\` ou `$env:USERPROFILE\` |
| Terminal | Terminal (zsh) | PowerShell |

---

## PROBLEMAS COMUNS

| Erro | Causa | Solução |
|------|-------|---------|
| `python: command not found` | Python não no PATH | Reinstalar marcando "Add to PATH" |
| `No module named laspy` | Bibliotecas não instaladas | Rodar SETUP.bat de novo |
| `redtech.bat não reconhecido` | Não está na pasta certa | `cd` para LIDAR_tests primeiro |
| CloudCompare não abre | Instalado em local custom | Abrir manualmente o .las em sessoes\ |
| Caminho com espaço dá erro | Falta aspas | Sempre usar aspas: `"C:\...\Teste 1"` |
| Acentos estranhos no terminal | CMD antigo | Usar PowerShell ou Windows Terminal |

---

## ONDE FICAM OS RESULTADOS

Depois de rodar, cada sessão fica em:

```
C:\Users\SEU_USUARIO\Downloads\LIDAR_tests\sessoes\
└── voo_20260527_142555\
    ├── input\          (cópias dos arquivos originais)
    ├── output\
    │   └── lidar_..._geo.las    ← arquivo final para CloudCompare
    ├── relatorio.md    ← resumo da sessão
    └── metrics.json    ← dados para comparação
```

Para abrir uma nuvem manualmente no CloudCompare:
- Navegue até `sessoes\voo_XXX\output\`
- Duplo-clique no arquivo `_geo.las`

---

## CHEAT SHEET (cola na parede)

```
SETUP (uma vez):
  1. Instalar Python (marcar Add to PATH)
  2. Duplo-clique em SETUP.bat
  3. Instalar CloudCompare

USO DIARIO:
  cd "%USERPROFILE%\Downloads\LIDAR_tests"
  .\redtech.bat "C:\...\Teste N" --batch
  .\redtech-compare.bat --all
```

---

*Guia v1.0 — RedTech Security — 28/05/2026*
*Scripts validados no Mac; primeira execução no Windows pode ter atritos.*
