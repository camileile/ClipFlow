# ClipFlow API

API FastAPI responsável por validar URLs públicas do YouTube, extrair metadados
reais e preparar downloads MP4 ou MP3 com `yt-dlp`. A análise usa
`download=False`; o download ocorre somente pelo endpoint dedicado e usa
diretórios temporários.

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
executável `node` disponível no `PATH`.

Downloads MP4 com streams separados e todas as conversões MP3 exigem os
executáveis `ffmpeg` e `ffprobe`. No Windows:

```powershell
winget install --id Gyan.FFmpeg --exact
ffmpeg -version
ffprobe -version
```

A API aplica limite de 30 minutos e 750 MiB, aceita MP3 apenas em 128, 192, 256
ou 320 kbps, não recebe caminhos nem seletores internos do cliente e remove os
arquivos temporários após a resposta. O bitrate MP3 configura a saída da
conversão e não representa ganho sobre a qualidade original.

A API fica disponível em `http://localhost:8000` e sua documentação interativa
em `http://localhost:8000/docs`.

## Testes

```bash
python -m pytest
```

Os testes usam mocks e não fazem requisições reais ao YouTube nem downloads de
mídia.
