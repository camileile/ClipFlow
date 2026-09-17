# ClipFlow

**Baixe. Converta. Simples assim.**

O ClipFlow é a fundação de uma aplicação web para análise, download e conversão
de mídias. Esta primeira fase entrega a experiência de produto e a comunicação
entre frontend e backend usando apenas respostas demonstrativas.

> **Status atual:** não existem downloads, conversões ou acesso a plataformas
> externas. A API apenas valida a URL e devolve metadados mockados.

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
│   ├── app/main.py           # Aplicação e configuração de CORS
│   ├── app/schemas.py        # Modelos de entrada e saída
│   └── tests/                # Testes dos endpoints
├── .gitignore
└── README.md
```

O frontend mantém a página como Server Component e restringe JavaScript no
cliente aos componentes que precisam de interação. A integração HTTP fica
isolada em `src/lib/api.ts`, com respostas verificadas em tempo de execução e
tipadas em `src/types/media.ts`.

O backend separa rotas e schemas, mas evita camadas adicionais enquanto ainda
não há regras de negócio ou persistência. O CORS aceita apenas as origens locais
esperadas nas portas `3000` e `3001`.

## Tecnologias

- Next.js 16 com App Router
- React 19
- TypeScript 5
- Tailwind CSS 4
- Python 3.13
- FastAPI 0.141
- Pydantic 2.13
- Uvicorn 0.53
- Pytest 9

## Requisitos

- Node.js 20.9 ou superior
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

Recebe uma URL válida:

```json
{
  "url": "https://www.youtube.com/watch?v=demo"
}
```

E devolve uma prévia demonstrativa, sem acessar o endereço informado:

```json
{
  "success": true,
  "platform": "youtube",
  "title": "Preview demonstrativo",
  "author": "Canal",
  "duration": 0,
  "thumbnail": null
}
```

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

Os testes cobrem o health check, análise de uma URL do YouTube, uma plataforma
desconhecida e a rejeição de URL inválida.

## Escopo desta fase

Implementado:

- base Next.js responsiva com temas claro e escuro;
- estados de campo vazio, URL inválida, carregamento, sucesso e erro;
- card de prévia e controles visuais de formato e qualidade;
- indicação das plataformas planejadas;
- API FastAPI com health check e análise simulada;
- integração frontend/backend via variável de ambiente;
- testes básicos da API.

Ainda não implementado:

- download ou conversão de mídia;
- yt-dlp, FFmpeg, scraping ou acesso a serviços externos;
- autenticação, banco de dados, filas ou armazenamento;
- Instagram, TikTok ou X/Twitter;
- Docker, pagamentos ou analytics.

## Próximos passos sugeridos

1. Definir regras de uso e requisitos funcionais para downloads reais.
2. Criar uma camada de serviços no backend quando houver lógica de negócio.
3. Implementar análise real do YouTube com testes e limites de segurança.
4. Adicionar o pipeline de conversão e acompanhamento de progresso.
5. Expandir plataformas somente após estabilizar o primeiro fluxo.
