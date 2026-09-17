# ClipFlow API

API FastAPI responsável, nesta fase, por validar URLs e devolver uma análise
demonstrativa. Nenhum conteúdo externo é acessado ou baixado.

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

A API fica disponível em `http://localhost:8000` e sua documentação interativa
em `http://localhost:8000/docs`.

## Testes

```bash
python -m pytest
```

