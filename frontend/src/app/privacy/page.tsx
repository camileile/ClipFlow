import type { Metadata } from "next";

import { LegalWindow } from "@/components/legal-window";

export const metadata: Metadata = {
  title: "Privacidade",
  description: "Como o ClipFlow processa URLs, arquivos temporários e dados técnicos.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalWindow title="Privacidade" subtitle="Como seus dados são tratados">
      <p>
        O ClipFlow recebe a URL informada para consultar a plataforma de origem e
        preparar a mídia solicitada. Não é necessário criar conta.
      </p>
      <h2>Arquivos e jobs temporários</h2>
      <p>
        Downloads são processados em diretórios temporários. Arquivos prontos,
        jobs cancelados e falhas expiram automaticamente, mas podem permanecer por
        alguns minutos até a retirada ou limpeza programada. Reiniciar o backend
        remove o estado dos jobs em memória.
      </p>
      <h2>Logs técnicos</h2>
      <p>
        O servidor pode registrar identificadores de requisição, endpoint,
        plataforma, status, duração e categorias de erro para diagnóstico. O
        projeto não precisa de cookies de conta e não registra mídia binária,
        senhas ou cookies das plataformas suportadas.
      </p>
      <h2>Serviços de terceiros</h2>
      <p>
        As plataformas de origem e o provedor de hospedagem possuem políticas
        próprias. O ClipFlow não controla como esses terceiros tratam requisições.
      </p>
    </LegalWindow>
  );
}
