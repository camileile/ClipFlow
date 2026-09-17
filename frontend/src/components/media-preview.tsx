import Image from "next/image";

import {
  CheckIcon,
  DownloadIcon,
  PlayIcon,
  VideoIcon,
} from "@/components/icons";
import { formatDuration } from "@/lib/format-duration";
import type { MediaFormat, MediaInfo, MediaQuality } from "@/types/media";

interface MediaPreviewProps {
  data: MediaInfo | null;
  format: MediaFormat;
  quality: MediaQuality;
  isLoading: boolean;
  onFormatChange: (format: MediaFormat) => void;
  onQualityChange: (quality: MediaQuality) => void;
}

const formatOptions: Array<{
  value: MediaFormat;
  label: string;
  description: string;
}> = [
  { value: "mp4", label: "MP4", description: "Vídeo" },
  { value: "mp3", label: "MP3", description: "Áudio" },
];

export function MediaPreview({
  data,
  format,
  quality,
  isLoading,
  onFormatChange,
  onQualityChange,
}: MediaPreviewProps) {
  const title = isLoading
    ? "Consultando o YouTube..."
    : (data?.title ?? "Seu vídeo aparecerá aqui");
  const author = isLoading
    ? "Isso pode levar alguns segundos"
    : (data?.author ?? (data ? "Canal não informado" : "Canal"));
  const duration = data ? formatDuration(data.duration) : "00:00";
  const platform = data || isLoading ? "YouTube" : "Prévia";

  return (
    <section
      className="relative overflow-hidden rounded-[1.4rem] border border-line bg-surface-elevated p-4 sm:p-5"
      aria-label="Prévia da mídia"
      aria-busy={isLoading}
    >
      {isLoading && (
        <div className="absolute inset-x-0 top-0 h-0.5 overflow-hidden bg-accent-soft">
          <div className="loading-bar h-full w-1/3 bg-accent" />
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-[1.05fr_1fr] md:gap-6">
        <div className="group relative aspect-video overflow-hidden rounded-2xl border border-line bg-preview">
          {data?.thumbnail ? (
            <>
              <Image
                src={data.thumbnail}
                alt={`Miniatura de ${data.title}`}
                fill
                sizes="(max-width: 767px) 100vw, 50vw"
                className="object-cover"
              />
              <div className="absolute inset-0 [background:linear-gradient(to_top,rgb(2_6_23/0.65),transparent_58%)]" />
            </>
          ) : (
            <div
              className={`absolute inset-0 opacity-60 [background-image:linear-gradient(to_right,var(--grid-line)_1px,transparent_1px),linear-gradient(to_bottom,var(--grid-line)_1px,transparent_1px)] [background-size:28px_28px] ${
                isLoading ? "animate-pulse" : ""
              }`}
            />
          )}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="grid size-16 place-items-center rounded-full border border-white/15 bg-slate-950/80 text-white shadow-xl backdrop-blur-sm transition duration-300 group-hover:scale-105">
              {data ? (
                <PlayIcon className="ml-0.5 size-7" />
              ) : (
                <VideoIcon className="size-7" />
              )}
            </div>
          </div>
          <div className="absolute inset-x-3 bottom-3 flex items-center justify-between">
            <span className="rounded-full border border-white/10 bg-slate-950/75 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-sm">
              {platform}
            </span>
            <span className="rounded-md bg-slate-950/80 px-2 py-1 font-mono text-[11px] font-medium text-white">
              {duration}
            </span>
          </div>
        </div>

        <div className="flex min-w-0 flex-col">
          <div className="mb-5">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-accent">
              {data && (
                <span className="grid size-4 place-items-center rounded-full bg-success text-white">
                  <CheckIcon className="size-3" />
                </span>
              )}
              {data
                ? "Análise concluída"
                : isLoading
                  ? "Analisando vídeo"
                  : "Aguardando seu link"}
            </div>
            <h2 className="truncate text-lg font-semibold tracking-[-0.02em] text-foreground sm:text-xl">
              {title}
            </h2>
            <p className="mt-1 text-sm text-muted">{author}</p>
          </div>

          <fieldset className="mb-4">
            <legend className="mb-2 text-xs font-semibold text-foreground">
              Formato
            </legend>
            <div className="grid grid-cols-2 gap-2">
              {formatOptions.map((option) => (
                <label
                  key={option.value}
                  className={`cursor-pointer rounded-xl border px-3 py-2.5 transition focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent ${
                    format === option.value
                      ? "border-accent bg-accent-soft text-accent-strong"
                      : "border-line bg-surface text-muted hover:border-accent/35 hover:text-foreground"
                  }`}
                >
                  <input
                    type="radio"
                    name="format"
                    value={option.value}
                    checked={format === option.value}
                    onChange={() => onFormatChange(option.value)}
                    className="sr-only"
                  />
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{option.label}</span>
                    <span className="text-[11px] opacity-70">
                      {option.description}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <label className="mb-4 block text-xs font-semibold text-foreground">
            <span className="mb-2 block">Qualidade</span>
            <select
              value={quality}
              onChange={(event) =>
                onQualityChange(event.target.value as MediaQuality)
              }
              className="h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm font-medium text-foreground outline-none transition hover:border-accent/35 focus:border-accent focus:ring-3 focus:ring-accent-soft"
            >
              <option value="best">Melhor qualidade</option>
              {data?.qualities.map((availableQuality) => (
                <option
                  key={availableQuality}
                  value={`${availableQuality}p`}
                >
                  {availableQuality}p
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            disabled
            className="mt-auto flex h-11 w-full cursor-not-allowed items-center justify-center gap-2 rounded-xl border border-line bg-disabled text-sm font-semibold text-disabled-text opacity-90"
            title="Downloads serão implementados em uma próxima etapa"
          >
            <DownloadIcon className="size-4" />
            Download em breve
          </button>
        </div>
      </div>
    </section>
  );
}
