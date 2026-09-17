"use client";

import { useState, type FormEvent } from "react";

import { ArrowRightIcon, LinkIcon } from "@/components/icons";
import { MediaPreview } from "@/components/media-preview";
import { analyzeMedia, ApiRequestError, downloadMedia } from "@/lib/api";
import type { MediaFormat, MediaInfo, MediaQuality } from "@/types/media";

type RequestStatus =
  | "idle"
  | "analyzing"
  | "ready"
  | "downloading"
  | "success"
  | "error";

function isValidWebUrl(value: string): boolean {
  try {
    const parsedUrl = new URL(value);
    return parsedUrl.protocol === "http:" || parsedUrl.protocol === "https:";
  } catch {
    return false;
  }
}

export function DownloaderPanel() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<RequestStatus>("idle");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<MediaInfo | null>(null);
  const [format, setFormat] = useState<MediaFormat>("mp4");
  const [quality, setQuality] = useState<MediaQuality>("best");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedUrl = url.trim();

    if (!normalizedUrl) {
      setStatus("error");
      setMessage("Cole um link para começar a análise.");
      return;
    }

    if (!isValidWebUrl(normalizedUrl)) {
      setStatus("error");
      setMessage(
        "Use um endereço completo, como https://www.youtube.com/watch?v=...",
      );
      return;
    }

    setPreview(null);
    setQuality("best");
    setStatus("analyzing");
    setMessage("Consultando os metadados públicos do vídeo...");

    try {
      const result = await analyzeMedia(normalizedUrl);
      setPreview(result.media);
      setStatus("ready");
      setMessage("Vídeo analisado. Escolha a qualidade para baixar o MP4.");
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof ApiRequestError
          ? error.message
          : "Ocorreu um erro inesperado. Tente novamente.",
      );
    }
  }

  async function handleDownload() {
    if (!preview || format !== "mp4" || status === "downloading") {
      return;
    }

    const selectedQuality =
      quality === "best"
        ? preview.qualities[0]
        : Number.parseInt(quality.replace(/p$/, ""), 10);

    if (!selectedQuality || !preview.qualities.includes(selectedQuality)) {
      setStatus("error");
      setMessage("Escolha uma qualidade disponível antes de baixar.");
      return;
    }

    setStatus("downloading");
    setMessage("Preparando o MP4. Esta etapa pode levar alguns minutos...");

    try {
      const result = await downloadMedia(
        {
          url: preview.original_url,
          format: "mp4",
          quality: selectedQuality,
        },
        preview.title,
      );
      setStatus("success");
      setMessage(`Download iniciado: ${result.filename}`);
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof ApiRequestError
          ? error.message
          : "Não foi possível concluir o download. Tente novamente.",
      );
    }
  }

  const isAnalyzing = status === "analyzing";
  const isDownloading = status === "downloading";
  const isBusy = isAnalyzing || isDownloading;
  const messageColor =
    status === "error"
      ? "text-danger"
      : status === "success" || status === "ready"
        ? "text-success-strong"
        : "text-muted";

  return (
    <div className="mx-auto w-full max-w-5xl rounded-[1.8rem] border border-line bg-panel p-3 shadow-panel backdrop-blur-xl sm:p-4 lg:p-5">
      <form onSubmit={handleSubmit} noValidate>
        <label
          htmlFor="media-url"
          className="mb-2.5 ml-1 block text-sm font-semibold text-foreground"
        >
          Link da mídia
        </label>
        <div className="flex flex-col gap-2.5 rounded-2xl border border-line-strong bg-surface p-2 transition focus-within:border-accent focus-within:ring-4 focus-within:ring-accent-soft sm:flex-row">
          <div className="flex min-w-0 flex-1 items-center gap-3 px-2 sm:px-3">
            <LinkIcon className="size-5 shrink-0 text-muted" />
            <input
              id="media-url"
              name="url"
              type="url"
              inputMode="url"
              autoComplete="url"
              value={url}
              disabled={isDownloading}
              onChange={(event) => {
                setUrl(event.target.value);
                if (preview !== null) {
                  setPreview(null);
                  setQuality("best");
                }
                if (status !== "idle") {
                  setStatus("idle");
                  setMessage("");
                }
              }}
              placeholder="Cole um link do YouTube..."
              aria-describedby="url-feedback"
              aria-invalid={status === "error" && preview === null}
              className="h-12 min-w-0 flex-1 bg-transparent text-base text-foreground outline-none placeholder:text-placeholder"
            />
          </div>
          <button
            type="submit"
            disabled={isBusy}
            className="group flex h-12 items-center justify-center gap-2 rounded-xl bg-accent px-6 text-sm font-bold text-white shadow-accent transition hover:-translate-y-0.5 hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-wait disabled:translate-y-0 disabled:opacity-70"
          >
            {isAnalyzing ? (
              <>
                <span className="size-4 animate-spin rounded-full border-2 border-white/35 border-t-white" />
                Analisando
              </>
            ) : isDownloading ? (
              "Aguarde"
            ) : (
              <>
                Analisar
                <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" />
              </>
            )}
          </button>
        </div>
        <div className="min-h-9 px-1 pt-2.5" aria-live="polite">
          <p id="url-feedback" className={`text-sm ${messageColor}`}>
            {message || "A análise consulta somente metadados públicos do YouTube."}
          </p>
        </div>
      </form>

      <MediaPreview
        data={preview}
        format={format}
        quality={quality}
        isLoading={isAnalyzing}
        isDownloading={isDownloading}
        onDownload={handleDownload}
        onFormatChange={(nextFormat) => {
          setFormat(nextFormat);
          if (preview) {
            setStatus("ready");
            setMessage(
              nextFormat === "mp3"
                ? "MP3 estará disponível em uma próxima etapa."
                : "Escolha a qualidade para baixar o MP4.",
            );
          }
        }}
        onQualityChange={setQuality}
      />
    </div>
  );
}
