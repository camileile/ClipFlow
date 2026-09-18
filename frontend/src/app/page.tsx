import { DownloaderPanel } from "@/components/downloader-panel";

export default function Home() {
  return (
    <main className="desktop-shell min-h-screen px-2 py-3 text-foreground sm:px-5 sm:py-7 lg:px-8 lg:py-10">
      <div className="mx-auto w-full max-w-[1120px]">
        <p className="desktop-caption mb-2 px-1 text-[13px] font-bold text-white/85 [text-shadow:1px_1px_0_rgb(0_67_78/0.8)] sm:mb-3">
          ClipFlow Download Manager
        </p>
        <DownloaderPanel />
        <p className="mx-auto mt-3 max-w-3xl text-center text-[12px] leading-5 text-white/80 [text-shadow:1px_1px_0_rgb(0_65_76/0.85)] sm:text-[13px]">
          Use o ClipFlow somente para conteúdo que você tenha permissão ou
          direito de baixar.
        </p>
      </div>
    </main>
  );
}
