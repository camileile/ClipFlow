import Image from "next/image";

import {
  CheckIcon,
  DownloadIcon,
  PlayIcon,
  VideoIcon,
} from "@/components/icons";
import { formatDuration } from "@/lib/format-duration";
import {
  SUPPORTED_MP3_BITRATES,
  type AudioQuality,
  type MediaFormat,
  type MediaInfo,
  type MediaPlatform,
  type MediaQuality,
} from "@/types/media";

interface MediaPreviewProps {
  data: MediaInfo | null;
  platform: MediaPlatform | null;
  format: MediaFormat;
  quality: MediaQuality;
  audioQuality: AudioQuality;
  isLoading: boolean;
  isDownloading: boolean;
  onDownload: () => void;
  onAudioQualityChange: (quality: AudioQuality) => void;
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
  platform,
  format,
  quality,
  audioQuality,
  isLoading,
  isDownloading,
  onDownload,
  onAudioQualityChange,
  onFormatChange,
  onQualityChange,
}: MediaPreviewProps) {
  const title = isLoading
    ? "Lendo informações..."
    : (data?.title ?? "Nenhuma mídia carregada");
  const author = isLoading
    ? "Aguarde alguns segundos"
    : (data?.author ?? (data ? "Canal não informado" : "—"));
  const duration = data ? formatDuration(data.duration) : "00:00";
  const isBusy = isLoading || isDownloading;
  const platformLabel =
    platform === "tiktok"
      ? "TikTok"
      : platform === "youtube"
        ? "YouTube"
        : "Aguardando";
  const hasAudio = data?.formats.some((item) => item.type === "audio") ?? false;
  const canDownload = Boolean(
    data &&
      !isBusy &&
      (format === "mp3" ? hasAudio : data.qualities.length > 0),
  );

  return (
    <section
      className="grid gap-3 lg:grid-cols-[minmax(0,1.45fr)_minmax(270px,0.75fr)]"
      aria-label="Prévia da mídia"
      aria-busy={isBusy}
    >
      <div className="retro-group min-w-0">
        <h2 className="retro-group-title">
          <VideoIcon className="size-4 text-accent-strong" />
          Informações da mídia
          <span className="ml-auto flex items-center gap-1.5 font-normal text-[11px] text-muted">
            <span
              className={`status-led ${data ? "status-led-success" : isLoading ? "status-led-busy" : ""}`}
              aria-hidden="true"
            />
            {data ? "Mídia pronta" : isLoading ? "Consultando" : "Aguardando"}
          </span>
        </h2>
        <div className="retro-group-body grid gap-3 sm:grid-cols-[minmax(220px,1.05fr)_minmax(190px,0.95fr)]">
          <div className="retro-inset relative aspect-video min-w-0 overflow-hidden bg-preview">
            {data?.thumbnail ? (
              <Image
                src={data.thumbnail}
                alt={`Miniatura de ${data.title}`}
                fill
                sizes="(max-width: 639px) 100vw, (max-width: 1023px) 55vw, 38vw"
                className="object-cover"
              />
            ) : (
              <div
                className={`absolute inset-0 opacity-75 [background-image:linear-gradient(to_right,var(--grid-line)_1px,transparent_1px),linear-gradient(to_bottom,var(--grid-line)_1px,transparent_1px)] [background-size:18px_18px] ${isLoading ? "animate-pulse" : ""}`}
              />
            )}
            <div className="absolute inset-0 grid place-items-center">
              {!data && (
                <span className="grid size-14 place-items-center border border-white/45 bg-black/45 text-white shadow-md">
                  {isLoading ? (
                    <span className="size-6 animate-pulse border-2 border-white bg-white/20" />
                  ) : (
                    <VideoIcon className="size-7" />
                  )}
                </span>
              )}
            </div>
            <div className="absolute inset-x-2 bottom-2 flex items-center justify-between gap-2">
              <span className="border border-white/50 bg-black/75 px-2 py-1 text-[11px] font-bold text-white">
                ● {platformLabel}
              </span>
              <span className="border border-white/50 bg-black/75 px-2 py-1 font-mono text-[11px] text-white">
                {duration}
              </span>
            </div>
          </div>

          <dl className="retro-inset min-w-0 text-[13px]">
            <div className="border-b border-line p-2.5">
              <dt className="mb-1 font-bold text-muted">Título:</dt>
              <dd className="line-clamp-3 font-semibold leading-5 text-foreground">
                {title}
              </dd>
            </div>
            <div className="grid grid-cols-[72px_1fr] border-b border-line p-2.5">
              <dt className="font-bold text-muted">Canal:</dt>
              <dd className="min-w-0 truncate">{author}</dd>
            </div>
            <div className="grid grid-cols-[72px_1fr] border-b border-line p-2.5">
              <dt className="font-bold text-muted">Duração:</dt>
              <dd className="font-mono">{duration}</dd>
            </div>
            <div className="grid grid-cols-[72px_1fr] p-2.5">
              <dt className="font-bold text-muted">Origem:</dt>
              <dd className="flex items-center gap-2">
                <span className="status-led status-led-success" aria-hidden="true" />
                {platformLabel}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="retro-group min-w-0">
        <h2 className="retro-group-title">
          <DownloadIcon className="size-4 text-accent-strong" />
          Saída
        </h2>
        <div className="retro-group-body flex h-[calc(100%-32px)] flex-col">
          <fieldset>
            <legend className="mb-2 text-[13px] font-bold">Formato:</legend>
            <div className="grid grid-cols-2 gap-2">
              {formatOptions.map((option) => (
                <label
                  key={option.value}
                  className={`retro-button flex min-h-12 cursor-pointer items-center gap-2 px-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent ${format === option.value ? "retro-button-pressed bg-accent-soft!" : ""}`}
                >
                  <input
                    type="radio"
                    name="format"
                    value={option.value}
                    checked={format === option.value}
                    disabled={isBusy}
                    onChange={() => onFormatChange(option.value)}
                    className="size-4 accent-[var(--accent)]"
                  />
                  <span>
                    <span className="block font-bold">{option.label}</span>
                    <span className="block text-[11px] font-normal text-muted">
                      {option.description}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="my-3 h-px bg-line shadow-[0_1px_0_var(--line-light)]" />

          {format === "mp4" ? (
            <label className="block text-[13px] font-bold">
              <span className="mb-1.5 block">Qualidade do vídeo:</span>
              <select
                value={quality}
                disabled={!data || isBusy}
                onChange={(event) =>
                  onQualityChange(event.target.value as MediaQuality)
                }
                className="retro-inset h-10 min-w-0 w-full overflow-hidden text-ellipsis px-2 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-60"
              >
                <option value="best">Melhor qualidade disponível</option>
                {data?.qualities.map((availableQuality) => (
                  <option key={availableQuality} value={`${availableQuality}p`}>
                    {availableQuality}p
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="block text-[13px] font-bold">
              <span className="mb-1.5 block">Qualidade do áudio:</span>
              <select
                value={audioQuality}
                disabled={!data || isBusy}
                onChange={(event) =>
                  onAudioQualityChange(Number(event.target.value) as AudioQuality)
                }
                className="retro-inset h-10 min-w-0 w-full overflow-hidden text-ellipsis px-2 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-60"
              >
                {SUPPORTED_MP3_BITRATES.map((bitrate) => (
                  <option key={bitrate} value={bitrate}>
                    {bitrate} kbps
                  </option>
                ))}
              </select>
              <span className="mt-2 block text-[11px] font-normal leading-4 text-muted">
                O bitrate define a conversão; ele não aumenta a qualidade da fonte.
              </span>
            </label>
          )}

          <button
            type="button"
            disabled={!canDownload}
            onClick={onDownload}
            className="retro-button retro-button-primary mt-auto flex h-11 w-full items-center justify-center gap-2 px-4"
          >
            {isDownloading ? (
              <>
                <span className="size-3 animate-pulse border border-white bg-white/35" />
                {format === "mp3" ? "Preparando MP3..." : "Preparando MP4..."}
              </>
            ) : (
              <>
                {data ? <DownloadIcon className="size-4" /> : <PlayIcon className="size-4" />}
                {format === "mp3" ? "Baixar MP3" : "Baixar MP4"}
              </>
            )}
          </button>

          <p className="mt-2 flex items-center gap-1.5 text-[11px] text-muted">
            {data && <CheckIcon className="size-3 text-success-strong" />}
            {data ? "Configuração válida para esta mídia." : "Analise uma mídia para habilitar."}
          </p>
        </div>
      </div>
    </section>
  );
}
