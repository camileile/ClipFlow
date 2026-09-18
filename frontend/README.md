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
está indisponível e renderiza os metadados reais normalizados pela API. Após a
análise, o usuário pode escolher uma resolução MP4 ou um bitrate MP3. O mesmo
cliente recebe as duas respostas binárias, valida o tipo esperado e usa o nome
sugerido pelo backend. A interface informa que o bitrate MP3 é uma configuração
de conversão, não um aumento da qualidade original.
