# ClipFlow Frontend

Interface web do ClipFlow construída com Next.js, TypeScript, App Router e
Tailwind CSS.

## Configuração

```bash
npm install
cp .env.example .env.local
```

No arquivo `.env.local`, configure a URL da API:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Scripts

```bash
npm run dev        # servidor de desenvolvimento
npm run lint       # análise estática
npm run typecheck  # validação TypeScript
npm run build      # build de produção
npm run start      # execução do build
```

O fluxo de análise depende da API FastAPI disponível em
`NEXT_PUBLIC_API_URL`. A interface mostra mensagens amigáveis quando o backend
está indisponível e renderiza os metadados reais normalizados pela API. O botão
de download permanece desativado nesta etapa.
