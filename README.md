# ClipFlow

**Baixe. Converta. Simples assim.**

O ClipFlow é a fundação de uma aplicação web para análise, download e conversão
de mídias. A aplicação já consulta metadados reais de vídeos públicos do
YouTube e apresenta título, canal, duração, thumbnail e qualidades disponíveis.

> **Status atual:** a análise é real, mas nenhum arquivo é baixado ou convertido.
> MP3, FFmpeg e as demais plataformas continuam fora do escopo.

## Parte 2 — análise real do YouTube

O endpoint `POST /api/analyze` usa a API Python do `yt-dlp` para extrair somente
metadados, sempre com `download=False`. O serviço valida protocolo e hostname
antes de chamar o extrator, aceita apenas domínios do YouTube e normaliza a
resposta para um contrato próprio do ClipFlow.

O payload bruto do `yt-dlp` nunca é enviado ao navegador. Formatos redundantes
são reduzidos a opções representativas e as resoluções são deduplicadas e
ordenadas. Erros de vídeo privado, removido, indisponível ou falha externa são
convertidos em respostas HTTP amigáveis, sem expor detalhes internos.

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
│   ├── app/services/         # Validação e extração com yt-dlp
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
de domínio, integração com `yt-dlp`, normalização e classificação de erros ficam
no serviço YouTube. O CORS aceita apenas as origens locais esperadas nas portas
`3000` e `3001`.

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

## Requisitos

- Node.js 22 ou superior
- npm 10 ou superior
- Python 3.11 ou superior

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
isso, o executável `node` precisa estar disponível no `PATH`. FFmpeg não é
necessário nesta etapa.

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

Os testes não acessam o YouTube. A camada de extração é substituída por mocks e
a suíte cobre health check, contrato de sucesso, URL inválida, domínio não
suportado, vídeo indisponível, erro inesperado, campos ausentes, normalização de
qualidades e a garantia de `download=False`.

## Escopo desta fase

Implementado:

- base Next.js responsiva com temas claro e escuro;
- estados de campo vazio, URL inválida, carregamento, sucesso e erro;
- thumbnail, título, canal, duração e qualidades reais do YouTube;
- card de prévia e controles visuais de formato e qualidade;
- indicação das plataformas planejadas;
- API FastAPI com health check e análise real de metadados;
- validação restrita a hosts do YouTube e timeout/retries limitados;
- integração frontend/backend via variável de ambiente;
- testes determinísticos da API e do serviço YouTube.

Ainda não implementado:

- download ou conversão de mídia;
- FFmpeg, conversão MP3 ou progresso de download;
- autenticação, banco de dados, filas ou armazenamento;
- Instagram, TikTok ou X/Twitter;
- Docker, pagamentos ou analytics.

## Próximos passos sugeridos

1. Definir regras de uso e requisitos funcionais para downloads reais.
2. Implementar download MP4 preservando os limites de segurança atuais.
3. Adicionar conversão MP3 somente quando o uso de FFmpeg for planejado.
4. Projetar acompanhamento de progresso sem bloquear requisições HTTP.
5. Expandir plataformas somente após estabilizar o fluxo do YouTube.
