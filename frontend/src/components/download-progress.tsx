import { DownloadIcon } from "@/components/icons";
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
  "Transferindo arquivo pronto": "Enviando arquivo ao navegador",
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

  return (
    <section
      className="retro-group"
      aria-live="polite"
      aria-label="Progresso do download"
    >
      <h2 className="retro-group-title">
        <DownloadIcon className="size-4 text-accent-strong" />
        Status do download
        <span className="ml-auto flex items-center gap-1.5 font-normal text-[11px] text-muted">
          <span className="status-led status-led-busy" aria-hidden="true" />
          Job ativo
        </span>
      </h2>
      <div className="retro-group-body">
        <div className="mb-2 flex items-center justify-between gap-3 text-[13px]">
          <p className="min-w-0 truncate">
            <strong>Status:</strong> {stage}
          </p>
          <strong className="shrink-0 font-mono text-accent-strong">
            {progress === null ? "—" : `${Math.round(progress)}%`}
          </strong>
        </div>

        {progress !== null ? (
          <div
            className="retro-progress-track"
            role="progressbar"
            aria-label={stage}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress)}
          >
            <div
              className="retro-progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
        ) : (
          <div
            className="retro-progress-track"
            role="progressbar"
            aria-label={`${stage}, progresso indeterminado`}
          >
            <div className="retro-progress-fill loading-bar w-1/3" />
          </div>
        )}

        <dl className="mt-3 grid grid-cols-2 border border-line sm:grid-cols-4">
          <div className="border-b border-r border-line bg-surface px-2.5 py-2 sm:border-b-0">
            <dt className="text-[11px] font-bold text-muted">Transferido</dt>
            <dd className="mt-0.5 truncate font-mono text-[12px]">
              {downloaded && total ? `${downloaded} / ${total}` : downloaded ?? "—"}
            </dd>
          </div>
          <div className="border-b border-line bg-surface px-2.5 py-2 sm:border-b-0 sm:border-r">
            <dt className="text-[11px] font-bold text-muted">Velocidade</dt>
            <dd className="mt-0.5 font-mono text-[12px]">{speed ?? "—"}</dd>
          </div>
          <div className="border-r border-line bg-surface px-2.5 py-2">
            <dt className="text-[11px] font-bold text-muted">Tempo restante</dt>
            <dd className="mt-0.5 font-mono text-[12px]">{eta ?? "—"}</dd>
          </div>
          <div className="bg-surface px-2.5 py-2">
            <dt className="text-[11px] font-bold text-muted">Processamento</dt>
            <dd className="mt-0.5 truncate font-mono text-[12px]">
              {job.status === "processing" ? "FFmpeg" : "yt-dlp"}
            </dd>
          </div>
        </dl>

        <div className="mt-3 flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
          <p className="text-[11px] leading-4 text-muted">
            {job.status === "processing"
              ? "Processamento local em andamento. O percentual fica indeterminado nesta etapa."
              : "Os valores são informados diretamente pelo servidor."}
          </p>
          {canCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={isCancelling}
              className="retro-button retro-button-danger min-w-28 px-4"
            >
              {isCancelling ? "Cancelando..." : "Cancelar"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
