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
análise, o usuário pode escolher uma resolução MP4 ou um bitrate MP3. A interface
cria um job, acompanha progresso real por SSE, mostra velocidade e ETA quando
disponíveis, identifica a fase de FFmpeg e permite cancelar. Ao receber o evento
`ready`, busca o arquivo, valida o tipo e usa o nome sugerido pelo backend.

Jobs não são recuperados depois de recarregar a página nesta etapa. A interface
informa que o bitrate MP3 é uma configuração de conversão, não um aumento da
qualidade original.
