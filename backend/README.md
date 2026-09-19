# ClipFlow API

API FastAPI responsável por validar URLs públicas do YouTube, TikTok, Instagram
e X/Twitter, extrair metadados reais e preparar downloads MP4 ou MP3 com
`yt-dlp`. A análise usa
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
ou 320 kbps e não recebe caminhos nem seletores internos do cliente. O bitrate
MP3 configura a saída da conversão e não representa ganho sobre a qualidade
original.

## Download jobs

O fluxo recomendado cria um job com `POST /api/download/jobs`, acompanha
progresso, velocidade, ETA e estágios por SSE em
`GET /api/download/jobs/{job_id}/events`, cancela com `DELETE` no mesmo recurso
e retira o arquivo pronto em `GET /api/download/jobs/{job_id}/file`.

Jobs são guardados somente em memória e executados em threads. Reiniciar a API
remove o estado. Arquivos prontos expiram após 15 minutos; falhas e cancelamentos
expiram após 5 minutos. Depois da entrega, o diretório temporário é removido.
Durante FFmpeg o progresso é indeterminado. O cancelamento impede a entrega,
mas não encerra à força um processo FFmpeg que já tenha começado.
Em downloads fragmentados, a interrupção pode aguardar o fragmento atual terminar
para permitir que o `yt-dlp` feche os arquivos temporários com segurança.

`POST /api/download` permanece disponível temporariamente para compatibilidade.

A API fica disponível em `http://localhost:8000` e sua documentação interativa
em `http://localhost:8000/docs`.

`GET /health` é um liveness check simples. `GET /ready` verifica FFmpeg,
FFprobe e escrita na raiz temporária sem acessar serviços externos.

## Produção

Copie os nomes de configuração de `.env.example` para o painel do provedor. O
backend aplica CORS por allowlist, rate limits por IP, limite global e por
cliente para jobs, request IDs e logs JSON. Endereços encaminhados só são
aceitos quando o peer pertence a `TRUSTED_PROXY_IPS`.

Execute somente um worker enquanto jobs e rate limits forem mantidos em memória:

```bash
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips="IP_DO_PROXY"
```

HTTPS deve terminar no provedor/reverse proxy. O proxy deve aplicar body limit
baixo, permitir conexões SSE longas e desabilitar buffering na rota de eventos.
Reiniciar o processo cancela jobs e remove temporários controlados; jobs não são
recuperados. A documentação interativa é desabilitada quando
`APP_ENV=production`.

## Testes

```bash
python -m pytest
```

Os testes usam mocks e não fazem requisições reais ao YouTube, TikTok, Instagram
ou X/Twitter nem downloads de mídia. A suíte inclui detecção de plataforma,
normalização, lifecycle, SSE,
throttle, TTL, cancelamento e concorrência entre jobs independentes.

## Plataformas suportadas

- YouTube: vídeos públicos em MP4 e MP3.
- TikTok: vídeos públicos em MP4 e MP3.
- Instagram: Reels públicos e posts públicos com um único vídeo em MP4 e MP3
  quando houver áudio.
- X/Twitter: posts públicos com um único vídeo ou mídia animada em MP4 e MP3
  quando houver áudio.

O Instagram não oferece suporte a Stories, mídia privada, login, carrosséis
completos ou posts somente com imagem. A disponibilidade depende do extractor;
o serviço não usa cookies, browser automation nem remove watermark ou branding.
No X/Twitter, contas protegidas, Spaces, threads completas, posts sem vídeo e
múltiplos vídeos não representáveis não são suportados. Mídias silenciosas podem
ser baixadas em MP4, mas são rejeitadas no fluxo MP3.
