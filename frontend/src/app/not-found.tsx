import type { Metadata } from "next";
import Link from "next/link";

import { ClipFlowIcon } from "@/components/icons";

export const metadata: Metadata = {
  title: "404 — Arquivo não encontrado",
  description: "A página solicitada não foi encontrada no ClipFlow.",
};

export default function NotFound() {
  return (
    <main className="desktop-shell grid min-h-screen place-items-center px-3 py-8 text-foreground">
      <section className="retro-window w-full max-w-xl" aria-labelledby="not-found-title">
        <div className="retro-titlebar">
          <span className="flex items-center gap-2 text-sm font-bold text-white">
            <span className="retro-app-icon" aria-hidden="true">
              <ClipFlowIcon className="size-4" />
            </span>
            ClipFlow — System Message
          </span>
        </div>
        <div className="retro-workspace">
          <div className="retro-alert retro-alert-warning flex gap-3 p-4 sm:p-5">
            <span className="retro-alert-icon" aria-hidden="true">!</span>
            <div>
              <h1 id="not-found-title" className="text-lg font-bold">404 — File Not Found</h1>
              <p className="mt-2 text-sm leading-6 text-muted">
                O endereço solicitado não existe ou foi movido.
              </p>
              <Link href="/" className="retro-button retro-button-primary mt-5 inline-flex min-h-9 items-center px-4">
                Voltar ao ClipFlow
              </Link>
            </div>
          </div>
        </div>
        <div className="retro-statusbar">
          <span className="retro-status-cell flex-1">Ready</span>
        </div>
      </section>
    </main>
  );
}
