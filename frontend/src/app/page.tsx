import { DownloaderPanel } from "@/components/downloader-panel";
import { PlayIcon, SparkleIcon } from "@/components/icons";
import { Platforms } from "@/components/platforms";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-canvas text-foreground">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[46rem] bg-hero-glow" />
      <div className="dot-grid pointer-events-none absolute inset-x-0 top-0 h-[38rem] opacity-45 [mask-image:linear-gradient(to_bottom,black,transparent)]" />

      <header className="relative z-20 border-b border-line/70 bg-canvas/75 backdrop-blur-xl">
        <div className="mx-auto flex h-17 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
          <a
            href="#inicio"
            className="group flex items-center gap-2.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
            aria-label="ClipFlow — página inicial"
          >
            <span className="grid size-9 place-items-center rounded-xl bg-accent text-white shadow-accent transition-transform group-hover:rotate-[-3deg] group-hover:scale-105">
              <PlayIcon className="ml-0.5 size-5" />
            </span>
            <span className="text-lg font-bold tracking-[-0.04em]">ClipFlow</span>
          </a>

          <div className="flex items-center gap-2 sm:gap-3">
            <a
              href="#sobre"
              className="rounded-full px-3 py-2 text-sm font-semibold text-muted transition hover:bg-surface-elevated hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:px-4"
            >
              Sobre
            </a>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main id="inicio" className="relative z-10">
        <section className="px-4 pb-18 pt-16 sm:px-6 sm:pb-24 sm:pt-22">
          <div className="mx-auto mb-9 max-w-3xl text-center sm:mb-11">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent-soft px-3 py-1.5 text-xs font-bold text-accent-strong shadow-xs">
              <SparkleIcon className="size-3.5" />
              Simples do link ao formato
            </div>
            <h1 className="text-balance text-4xl font-bold leading-[1.05] tracking-[-0.055em] text-foreground sm:text-6xl lg:text-7xl">
              Baixe. Converta.
              <span className="block text-accent">Simples assim.</span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-7 text-muted sm:mt-6 sm:text-lg sm:leading-8">
              Cole o link de um vídeo público do YouTube, confira os detalhes,
              escolha uma qualidade disponível e baixe em MP4 ou MP3.
            </p>
          </div>

          <DownloaderPanel />
          <p className="mx-auto mt-4 max-w-3xl text-center text-xs leading-5 text-muted">
            Use o ClipFlow apenas para conteúdo que você tenha permissão ou
            direito de baixar.
          </p>
        </section>

        <section className="border-y border-line bg-section px-4 py-18 sm:px-6 sm:py-22">
          <Platforms />
        </section>

        <section id="sobre" className="scroll-mt-20 px-4 py-18 sm:px-6 sm:py-24">
          <div className="mx-auto grid w-full max-w-5xl gap-8 rounded-[1.8rem] border border-line bg-surface p-6 shadow-card sm:p-9 md:grid-cols-[1fr_1.35fr] md:items-center md:gap-12">
            <div>
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-accent">
                Sobre o ClipFlow
              </p>
              <h2 className="text-2xl font-semibold tracking-[-0.035em] text-foreground sm:text-3xl">
                Menos etapas. Mais clareza.
              </h2>
            </div>
            <p className="text-sm leading-7 text-muted sm:text-base">
              O ClipFlow está sendo construído para transformar links de mídia
              em um fluxo direto e fácil de entender. Nesta etapa, a API
              consulta metadados públicos reais do YouTube e prepara downloads
              MP4 na resolução escolhida ou converte o melhor áudio disponível
              para MP3 no bitrate selecionado.
            </p>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-line px-4 py-7 sm:px-6">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 text-center text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:text-left">
          <p>© 2026 ClipFlow. Downloads MP4 e MP3.</p>
          <p>Feito para evoluir, sem atalhos desnecessários.</p>
        </div>
      </footer>
    </div>
  );
}
