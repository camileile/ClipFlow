import type { Metadata } from "next";

import { LegalWindow } from "@/components/legal-window";

export const metadata: Metadata = {
  title: "Termos de uso",
  description: "Condições simples para o uso responsável do ClipFlow.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <LegalWindow title="Termos de uso" subtitle="Uso responsável do ClipFlow">
      <p>
        Use o ClipFlow apenas para conteúdo que você tenha direito ou permissão
        para baixar. Você é responsável por respeitar direitos autorais, termos
        das plataformas e leis aplicáveis.
      </p>
      <h2>Limites do serviço</h2>
      <p>
        O ClipFlow não contorna DRM, paywalls, contas privadas ou conteúdo que
        exija login. A disponibilidade depende das plataformas e do extractor e
        pode mudar ou falhar quando serviços externos alterarem seu comportamento.
      </p>
      <h2>Sem garantia de disponibilidade</h2>
      <p>
        O serviço é fornecido como ferramenta utilitária, sujeito a limites de
        duração, tamanho, concorrência e taxa. Jobs são temporários e podem ser
        perdidos durante reinícios ou manutenção.
      </p>
      <p>
        Este texto é uma descrição simples das condições do projeto e não
        substitui aconselhamento jurídico.
      </p>
    </LegalWindow>
  );
}
