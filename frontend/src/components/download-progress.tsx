import { formatBytes, formatEta, formatSpeed } from "@/lib/format-transfer";
import type { DownloadJobState } from "@/types/media";

interface DownloadProgressProps {
  job: DownloadJobState;
  isCancelling: boolean;
  canCancel: boolean;
  onCancel: () => void;
}

const stageLabels: Record<string, string> = {
  Preparing: "Preparando download",
  "Downloading video": "Baixando vídeo",
  "Downloading audio": "Baixando áudio",
  "Finalizing download": "Finalizando arquivo",
  "Merging video and audio": "Unindo vídeo e áudio",
  "Converting to MP3": "Convertendo para MP3",
};

export function DownloadProgress({
  job,
  isCancelling,
  canCancel,
  onCancel,
}: DownloadProgressProps) {
  const progress = job.progress;
  const stage = stageLabels[job.stage] ?? job.stage;
  const downloaded = formatBytes(job.downloaded_bytes);
  const total = formatBytes(job.total_bytes);
  const speed = formatSpeed(job.speed);
  const eta = formatEta(job.eta);
  const details = [
    downloaded && total ? `${downloaded} de ${total}` : downloaded,
    speed,
    eta ? `${eta} restantes` : null,
  ].filter((value): value is string => Boolean(value));

  return (
    <section
      className="mb-4 rounded-2xl border border-accent/25 bg-accent-soft p-4"
      aria-live="polite"
      aria-label="Progresso do download"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground">{stage}</p>
          <p className="mt-1 text-xs text-muted">
            {job.status === "processing"
              ? "O FFmpeg está preparando o arquivo final."
              : details.join(" · ") || "Aguardando dados do servidor..."}
          </p>
        </div>
        {progress !== null && (
          <span className="shrink-0 font-mono text-sm font-semibold text-accent-strong">
            {Math.round(progress)}%
          </span>
        )}
      </div>

      {progress !== null ? (
        <div
          className="mt-3 h-2 overflow-hidden rounded-full bg-surface"
          role="progressbar"
          aria-label={stage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress)}
        >
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-200"
            style={{ width: `${progress}%` }}
          />
        </div>
      ) : (
        <div
          className="mt-3 h-2 overflow-hidden rounded-full bg-surface"
          role="progressbar"
          aria-label={`${stage}, progresso indeterminado`}
        >
          <div className="loading-bar h-full w-1/3 rounded-full bg-accent" />
        </div>
      )}

      {canCancel && (
        <button
          type="button"
          onClick={onCancel}
          disabled={isCancelling}
          className="mt-3 rounded-lg border border-line-strong bg-surface px-3 py-2 text-xs font-semibold text-foreground transition hover:border-danger hover:text-danger focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-wait disabled:opacity-60"
        >
          {isCancelling ? "Cancelando..." : "Cancelar"}
        </button>
      )}
    </section>
  );
}
