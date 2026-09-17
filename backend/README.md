# ClipFlow API

API FastAPI responsável por validar URLs públicas do YouTube e extrair
metadados reais com `yt-dlp`. A análise usa `download=False`: nenhum arquivo de
mídia é baixado ou convertido.

## Desenvolvimento

```bash
python -m venv .venv
```

No Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

O serviço usa `yt-dlp[default]`, incluindo `yt-dlp-ejs`, e habilita Node.js como
runtime dos desafios JavaScript do YouTube. Use Node.js 22 ou superior e deixe o
executável `node` disponível no `PATH`. FFmpeg não é necessário.

A API fica disponível em `http://localhost:8000` e sua documentação interativa
em `http://localhost:8000/docs`.

## Testes

```bash
python -m pytest
```

Os testes usam mocks e não fazem requisições reais ao YouTube.
