# Estrutura do Projeto

```text
.
├── ajr_app/
│   ├── ajr_desktop/
│   │   ├── app.py
│   │   └── settings.py
│   ├── assets/
│   ├── modules/
│   │   ├── core/
│   │   └── gui/
│   ├── manage.py
│   └── requirements.txt
├── bin/
│   ├── ajr-fastlio2-lvx.bat
│   └── ajr-fastlio2-lvx.sh
├── docs/
│   ├── APLICATIVO_AJR.md
│   ├── FASTLIO2_PIPELINE.md
│   ├── GUIA_WINDOWS.md
│   ├── PROJECT_STRUCTURE.md
│   ├── comparacao_linux.md
│   └── nota_cliente_processamento_reconstrucao.md
├── fastlio2/
│   ├── config/
│   ├── docker/
│   └── scripts/
├── outputs/
│   └── las/
├── scripts/
│   ├── converters/
│   │   ├── las_to_ply_ajr.py
│   │   ├── lvx_to_las_ajr.py
│   │   └── pcd_to_las_ajr.py
│   ├── diagnostics/
│   │   ├── analyze_lvx_v2.5.py
│   │   └── inspect_lvx_imu.py
│   ├── georef/
│   │   ├── las_geo_ajr.py
│   │   └── las_lio_geo_ajr.py
│   └── pipeline/
│       ├── ajr_compare.py
│       └── ajr_pipeline.py
├── ADICIONAR_AO_PATH.txt
├── README.md
├── SETUP.bat
├── ajr-compare.bat
├── ajr.bat
└── requirements.txt
```

## Responsabilidades

- `ajr_app`: interface desktop PySide6, execucao em segundo plano, salvamento e abertura no CloudCompare.
- `scripts/pipeline`: fluxo completo e comparacao de sessoes.
- `scripts/converters`: conversoes entre LVX, PCD, LAS e PLY.
- `scripts/georef`: georreferenciamento GNSS e LIO.
- `scripts/diagnostics`: ferramentas de inspecao e analise.
- `fastlio2`: ambiente Docker/ROS e execucao FAST-LIO2.
- `bin`: wrappers de execucao para usuario final.
- `outputs`: resultados locais nao versionados.
- `docs`: documentacao tecnica e operacional.

## Pontos de Entrada

```bash
.venv-wsl/bin/python ajr_app/manage.py
bin/ajr-fastlio2-lvx.sh arquivo.lvx fastlio2_output/sessao
python scripts/pipeline/ajr_pipeline.py pasta_da_sessao
python scripts/pipeline/ajr_compare.py --all
```
