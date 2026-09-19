import Link from "next/link";
import type { ReactNode } from "react";

import { ClipFlowIcon } from "@/components/icons";
import { SiteFooter } from "@/components/site-footer";

interface LegalWindowProps {
  title: string;
  subtitle: string;
  children: ReactNode;
}

export function LegalWindow({ title, subtitle, children }: LegalWindowProps) {
  return (
    <main className="desktop-shell min-h-screen px-2 py-3 text-foreground sm:px-5 sm:py-7 lg:px-8 lg:py-10">
      <div className="mx-auto w-full max-w-[850px]">
        <article className="retro-window">
          <div className="retro-titlebar">
            <div className="flex min-w-0 items-center gap-2">
              <span className="retro-app-icon" aria-hidden="true">
                <ClipFlowIcon className="size-4" />
              </span>
              <span className="truncate text-sm font-bold text-white [text-shadow:1px_1px_0_rgb(0_38_104/0.8)]">
                ClipFlow — {title}
              </span>
            </div>
          </div>
          <div className="retro-menubar">
            <Link href="/" className="px-2 py-1 underline-offset-2 hover:underline">
              Voltar ao ClipFlow
            </Link>
          </div>
          <div className="retro-workspace">
            <section className="retro-group">
              <header className="retro-group-title">{title}</header>
              <div className="retro-group-body legal-copy">
                <h1>{subtitle}</h1>
                {children}
              </div>
            </section>
          </div>
          <div className="retro-statusbar">
            <span className="retro-status-cell flex-1">Documento informativo</span>
            <span className="retro-status-cell status-version">ClipFlow v0.10</span>
          </div>
        </article>
        <SiteFooter />
      </div>
    </main>
  );
}
