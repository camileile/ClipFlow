# ClipFlow

**Baixe. Converta. Simples assim.**

O ClipFlow é uma aplicação web para análise, download e futura conversão de
mídias. A aplicação consulta metadados reais de vídeos públicos do YouTube e
TikTok, apresenta as qualidades disponíveis e permite baixar vídeos em MP4 ou
converter o áudio para MP3.

> **Status atual:** análise e downloads MP4/MP3 são reais para YouTube e TikTok.
> Instagram e X continuam fora do escopo.

## Supported Platforms

- **YouTube:** análise, MP4 e MP3.
- **TikTok:** análise, MP4 e MP3 para vídeos públicos que o extractor consiga
  acessar normalmente.
- **Instagram:** planejado.
- **X:** planejado.

O detector valida protocolo e hostname antes de chamar o `yt-dlp`; URLs curtas
oficiais do TikTok, como `vm.tiktok.com`, são entregues ao próprio extractor
para resolução. A disponibilidade depende do conteúdo público oferecido pela
plataforma. O ClipFlow não usa login, cookies, scraping manual, bypass de DRM ou
remoção de marca d'água; quando a mídia fornecida contém watermark, ela pode
permanecer no arquivo final.

## Parte 2 — análise real do YouTube

O endpoint `POST /api/analyze` usa a API Python do `yt-dlp` para extrair somente
metadados, sempre com `download=False`. O serviço valida protocolo e hostname
antes de chamar o extrator, aceita apenas domínios do YouTube e normaliza a
resposta para um contrato próprio do ClipFlow.

O payload bruto do `yt-dlp` nunca é enviado ao navegador. Formatos redundantes
são reduzidos a opções representativas e as resoluções são deduplicadas e
ordenadas. Erros de vídeo privado, removido, indisponível ou falha externa são
convertidos em respostas HTTP amigáveis, sem expor detalhes internos.

## Parte 7 — suporte ao TikTok

A detecção de plataforma agora é centralizada e reconhece hosts oficiais do
YouTube e TikTok por parsing de URL. Cada provider usa a API Python do `yt-dlp`
para extração, mas ambos retornam o mesmo contrato normalizado e seguem pelo
mesmo pipeline de download, jobs, progresso, cancelamento, limites e cleanup.

No TikTok, título/descrição, autor, duração, thumbnail e resoluções são usados
somente quando o extractor os fornece. MP4 aceita os formatos combinados comuns
da plataforma; MP3 pode extrair o áudio do stream combinado via FFmpeg. Nenhuma
técnica de remoção de watermark ou contorno de restrições é aplicada.

## Parte 3 — downloads MP4

O endpoint `POST /api/download` revalida a URL, consulta novamente os formatos
do vídeo e exige uma resolução realmente disponível. O seletor é construído
internamente: o navegador nunca envia IDs de formato, argumentos do FFmpeg,
nomes de arquivo ou caminhos do servidor.

Quando o YouTube oferece vídeo e áudio juntos em um MP4 compatível, esse
arquivo pode ser entregue diretamente. Quando os streams estão separados, o
`yt-dlp` usa FFmpeg para fazer merge/remux em um único MP4, sem recodificação
pesada. Cada requisição usa um diretório temporário próprio, removido depois que
a resposta termina ou imediatamente se ocorrer um erro.

Os limites iniciais são 30 minutos de duração e 750 MiB por arquivo. O limite
de tamanho é aplicado quando a estimativa está disponível e também é informado
ao `yt-dlp`. Vídeos com duração desconhecida não são iniciados, pois não é
possível comprovar que estão dentro do limite.

## Parte 4 — downloads MP3

O mesmo endpoint `POST /api/download` aceita agora uma requisição MP3 tipada. O
backend escolhe somente o melhor stream de áudio disponível e usa o
`FFmpegExtractAudio`, integrado ao `yt-dlp`, para gerar o arquivo final em 128,
192, 256 ou 320 kbps.

O bitrate representa a configuração do MP3 convertido. Ele não aumenta a
qualidade do áudio original disponibilizado pelo YouTube. O frontend alterna
entre resolução de vídeo e bitrate de áudio e nunca envia os dois campos na
mesma requisição.

MP4 e MP3 reutilizam validação de URL, limites, detecção de FFmpeg, diretórios
temporários, sanitização do nome, entrega binária e limpeza posterior. MP3
sempre exige `ffmpeg` e `ffprobe` disponíveis no `PATH`.

## Parte 5 — download jobs e progresso real

O fluxo principal usa jobs efêmeros em memória. `POST /api/download/jobs`
responde imediatamente com um UUID4; o pipeline bloqueante do `yt-dlp` e do
FFmpeg roda em uma thread, sem bloquear o event loop do FastAPI. O navegador
acompanha o job por SSE em `GET /api/download/jobs/{job_id}/events`.

Os progress hooks do `yt-dlp` fornecem bytes baixados, total conhecido ou
estimado, velocidade e ETA. As atualizações são limitadas a quatro por segundo.
Quando o FFmpeg assume o processamento, a interface troca para um indicador
indeterminado: não é criado um percentual fictício para merge ou conversão.

Quando o job fica pronto, `GET /api/download/jobs/{job_id}/file` entrega o
arquivo e só então remove o diretório temporário. `DELETE
/api/download/jobs/{job_id}` cancela jobs ativos; o hook interrompe o download
na próxima atualização. Se o FFmpeg já estiver executando, ele pode terminar o
processo atual, mas o job permanece cancelado e o arquivo nunca é exposto.
Em streams fragmentados, a interrupção pode aguardar o fragmento atual terminar
para que o `yt-dlp` libere seus arquivos com segurança; a entrega continua
bloqueada e os temporários são removidos assim que a operação puder encerrar.

Jobs prontos expiram após 15 minutos sem retirada. Jobs com falha ou cancelados
expiram após 5 minutos. Um processo periódico leve e os próprios acessos ao
manager executam a limpeza. Os jobs não são persistidos: reiniciar o backend
remove todo o estado e recarregar o frontend perde a referência do job atual.

## Interface

O ClipFlow usa uma interface autoral inspirada em utilitários desktop e software
da internet do início dos anos 2000. A janela principal reúne downloader,
atividade atual e informações do aplicativo em uma linguagem retrô adaptada para
desktop, tablet e celular, com modo diurno e um “retro night mode”.

A referência é exclusivamente estética. O projeto não utiliza assets, marcas ou
interfaces proprietárias da Microsoft ou do Windows.

## Arquitetura

```text
clipflow/
├── frontend/                 # Next.js, TypeScript e Tailwind CSS
│   ├── src/app/              # App Router, layout e página inicial
│   ├── src/components/       # Downloader, prévia, tema e plataformas
│   ├── src/lib/              # Cliente HTTP tipado
│   └── src/types/            # Contratos da API
├── backend/                  # FastAPI, Uvicorn e Pydantic
│   ├── app/api/              # Rotas HTTP
│   ├── app/schemas/          # Contratos de entrada e saída
│   ├── app/services/         # Análise, download, jobs e detecção do FFmpeg
│   ├── app/config.py         # Limites centralizados do download
│   ├── app/main.py           # Aplicação e configuração de CORS
│   └── tests/                # Testes de endpoints e normalização
├── .gitignore
└── README.md
```

O frontend mantém a página como Server Component e restringe JavaScript no
cliente aos componentes que precisam de interação. A integração HTTP fica
isolada em `src/lib/api.ts`, com respostas verificadas em tempo de execução e
tipadas em `src/types/media.ts`.

O backend mantém as rotas responsáveis apenas pelo protocolo HTTP. A validação
de domínio fica no detector central; os providers YouTube e TikTok cuidam da
extração específica e entregam um `MediaInfo` normalizado. Seleção de streams de
vídeo/áudio, conversão MP3, limites, nome seguro e ciclo dos arquivos temporários
ficam no serviço compartilhado de download. O `JobManager` protege o estado
concorrente, publica versões para SSE e controla cancelamento e TTL. O CORS
aceita apenas as origens locais esperadas nas portas `3000` e `3001` e expõe
somente o cabeçalho necessário para o nome do arquivo.

## Tecnologias

- Next.js 16 com App Router
- React 19
- TypeScript 5
- Tailwind CSS 4
- Python 3.13
- FastAPI 0.141
- Pydantic 2.13
- Uvicorn 0.53
- yt-dlp 2026.8.19
- yt-dlp-ejs 0.8.0
- Pytest 9
- FFmpeg 9 ou versão compatível, necessário quando vídeo e áudio estão separados

## Requisitos

- Node.js 22 ou superior
- npm 10 ou superior
- Python 3.11 ou superior
- FFmpeg e FFprobe disponíveis no `PATH` para downloads que exigem merge

As versões usadas durante o desenvolvimento foram Node.js `24.13.1`, npm
`11.8.0` e Python `3.13.14`.

## Instalação

Clone o repositório e acesse sua pasta:

```bash
git clone https://github.com/camileile/ClipFlow.git
cd ClipFlow
```

### Frontend

```bash
cd frontend
npm install
```

Crie o arquivo local de ambiente a partir do exemplo:

```bash
cp .env.example .env.local
```

No PowerShell, use:

```powershell
Copy-Item .env.example .env.local
```

### Backend

```bash
cd backend
python -m venv .venv
```

Ative o ambiente virtual no macOS/Linux:

```bash
source .venv/bin/activate
```

Ou no Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

Instale as dependências de desenvolvimento, que incluem os testes:

```bash
python -m pip install -r requirements-dev.txt
```

Para instalar somente as dependências de execução, use
`requirements.txt`.

O extra `yt-dlp[default]` instala os scripts `yt-dlp-ejs` usados nos desafios
atuais do YouTube. O serviço habilita o Node.js como runtime JavaScript; por
isso, o executável `node` precisa estar disponível no `PATH`.

### FFmpeg no Windows

O backend não instala FFmpeg automaticamente. No Windows, uma opção é o pacote
mantido por Gyan Doshi e distribuído pelo `winget`:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Feche e abra o terminal depois da instalação. Confirme os dois executáveis:

```powershell
ffmpeg -version
ffprobe -version
```

Se a qualidade escolhida já possuir vídeo e áudio em um único MP4, o download
pode não precisar do FFmpeg. Para streams separados, ambos os executáveis são
obrigatórios e a API retorna uma mensagem controlada quando não os encontra.

## Variáveis de ambiente

O frontend lê a seguinte variável:

| Variável | Valor local sugerido | Descrição |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL base pública da API |

O valor local padrão também é `http://localhost:8000`, mas manter o arquivo
`.env.local` torna a configuração explícita. Arquivos `.env` reais não são
versionados.

## Execução

Use dois terminais.

No primeiro, inicie a API:

```bash
cd backend
uvicorn app.main:app --reload
```

No segundo, inicie a interface:

```bash
cd frontend
npm run dev
```

Acesse:

- Interface: `http://localhost:3000`
- API: `http://localhost:8000`
- Documentação da API: `http://localhost:8000/docs`

## Endpoints atuais

### `GET /health`

Confirma que o serviço está disponível:

```json
{
  "status": "ok",
  "service": "clipflow-api"
}
```

### `POST /api/analyze`

Recebe uma URL pública válida do YouTube:

```json
{
  "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
}
```

Extrai e normaliza os metadados sem baixar a mídia:

```json
{
  "success": true,
  "platform": "youtube",
  "media": {
    "id": "jNQXAC9IVRw",
    "title": "Me at the zoo",
    "author": "jawed",
    "duration": 19,
    "thumbnail": "https://i.ytimg.com/...",
    "original_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "qualities": [240, 144],
    "formats": [
      {
        "format_id": "18",
        "type": "video",
        "extension": "mp4",
        "quality": 240,
        "fps": 30,
        "bitrate": null,
        "filesize": null
      }
    ]
  }
}
```

O array `formats` contém apenas representações controladas pelo ClipFlow, não a
resposta bruta do extrator. O conteúdo exato varia conforme o vídeo e a
disponibilidade informada pelo YouTube.

### `POST /api/download` — MP4

Recebe somente URL, formato MP4 e resolução exata:

```json
{
  "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
  "format": "mp4",
  "quality": 240
}
```

Em caso de sucesso, responde com o arquivo binário usando `Content-Type:
video/mp4` e `Content-Disposition: attachment`. O nome é derivado do título,
sanitizado no backend e limitado a um tamanho seguro. O contrato MP4 aceita
somente o campo de resolução e rejeita campos exclusivos de MP3.

### `POST /api/download` — MP3

Recebe URL, formato e um dos bitrates suportados:

```json
{
  "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
  "format": "mp3",
  "audio_quality": 192
}
```

A resposta usa `Content-Type: audio/mpeg` e sugere um nome `.mp3` seguro no
`Content-Disposition`. Valores fora de 128, 192, 256 e 320 kbps, campos
ausentes e combinações como MP3 com resolução de vídeo são rejeitados pelo
schema antes do processamento.

### Download jobs

O endpoint antigo `POST /api/download` continua disponível temporariamente para
compatibilidade. A interface usa o fluxo assíncrono:

```text
POST /api/download/jobs
GET  /api/download/jobs/{job_id}/events
GET  /api/download/jobs/{job_id}/file
DELETE /api/download/jobs/{job_id}
```

A criação recebe o mesmo contrato discriminado de MP4 ou MP3 e responde com:

```json
{
  "job_id": "1fe5bfe6-dfc7-4e73-9d54-04b0bfad12af",
  "status": "queued"
}
```

O stream SSE envia eventos nomeados `progress`, `ready`, `error` e `cancelled`,
além de comentários `: keepalive` a cada 10 segundos sem mudanças. O arquivo só
pode ser solicitado no estado `ready`; antes disso a API responde `409`.

## Validações

Frontend:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

Backend:

```bash
cd backend
python -m pytest
```

Os testes não acessam YouTube ou TikTok. As camadas de extração e download são
substituídas por mocks. A suíte cobre os cenários anteriores e também jobs concorrentes,
UUID, throttle, progresso determinado e indeterminado, velocidade, ETA, SSE,
keepalive, cancelamento, entrega MP4/MP3 e limpeza por resposta ou TTL.

## Escopo desta fase

Implementado:

- base Next.js responsiva com temas claro e escuro;
- estados de campo vazio, URL inválida, carregamento, sucesso e erro;
- thumbnail, título/descrição, autor, duração e qualidades reais de YouTube e TikTok;
- card de prévia e controles visuais de formato e qualidade;
- indicação das plataformas suportadas e planejadas;
- API FastAPI com health check e análise real de metadados;
- download MP4 real com resolução validada novamente no backend;
- merge/remux de vídeo e áudio separados usando FFmpeg quando necessário;
- entrega binária com nome seguro e limpeza posterior do diretório temporário;
- conversão MP3 em 128, 192, 256 ou 320 kbps usando somente o stream de áudio;
- jobs em memória com progresso real, velocidade, ETA, SSE e cancelamento;
- lifecycle do arquivo pronto com retirada posterior e TTL automático;
- validação restrita a hosts oficiais de YouTube e TikTok, com timeout/retries limitados;
- integração frontend/backend via variável de ambiente;
- testes determinísticos da API e dos providers YouTube/TikTok.

Ainda não implementado:

- persistência ou recuperação de jobs após reinício/refresh;
- autenticação, banco de dados, filas ou armazenamento;
- Instagram ou X/Twitter;
- Docker, pagamentos ou analytics.

## Próximos passos sugeridos

1. Avaliar Redis e workers externos antes de múltiplas instâncias ou cargas maiores.
2. Adicionar recuperação do job no frontend somente quando houver persistência.
3. Considerar metadados ID3 e capa apenas em uma etapa separada.
4. Avaliar novas plataformas somente em etapas próprias e sem duplicar o pipeline.
