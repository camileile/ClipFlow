import Link from "next/link";

import { siteConfig } from "@/lib/site-config";

export function SiteFooter() {
  return (
    <footer className="retro-footer mx-auto mt-3 max-w-3xl text-center text-[12px] leading-5 text-white/85 [text-shadow:1px_1px_0_rgb(0_65_76/0.85)] sm:text-[13px]">
      <p>
        Use o ClipFlow somente para conteúdo que você tenha permissão ou direito
        de baixar.
      </p>
      <nav className="mt-1.5 flex flex-wrap items-center justify-center gap-x-3 gap-y-1" aria-label="Links institucionais">
        <Link href="/privacy">Privacidade</Link>
        <Link href="/terms">Termos</Link>
        <a href={siteConfig.contactUrl} target="_blank" rel="noopener noreferrer">
          Contato
        </a>
        <a href={siteConfig.repositoryUrl} target="_blank" rel="noopener noreferrer">
          GitHub
        </a>
      </nav>
    </footer>
  );
}
