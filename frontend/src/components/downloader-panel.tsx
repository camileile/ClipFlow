"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { DownloadProgress } from "@/components/download-progress";
import { ArrowRightIcon, LinkIcon } from "@/components/icons";
import { MediaPreview } from "@/components/media-preview";
import {
  analyzeMedia,
  ApiRequestError,
  cancelDownloadJob,
  createDownloadJob,
  downloadJobFile,
  subscribeToDownloadJob,
} from "@/lib/api";
import type {
  AudioQuality,
  DownloadJobState,
  DownloadRequest,
  MediaFormat,
  MediaInfo,
  MediaQuality,
} from "@/types/media";

type PassiveStatus =
  | "idle"
  | "analyzing"
  | "ready"
  | "completed"
  | "cancelled"
  | "error";

type ActiveStatus = "queued" | "downloading" | "processing" | "retrieving";

type RequestState =
  | { status: PassiveStatus; message: string }
  | {
      status: ActiveStatus;
      message: string;
      jobId: string;
      job: DownloadJobState;
      isCancelling: boolean;
    };

const INITIAL_STATE: RequestState = { status: "idle", message: "" };

function isActiveState(
  state: RequestState,
): state is Extract<RequestState, { status: ActiveStatus }> {
  return ["queued", "downloading", "processing", "retrieving"].includes(
    state.status,
  );
}

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
  const [requestState, setRequestState] = useState<RequestState>(INITIAL_STATE);
  const [preview, setPreview] = useState<MediaInfo | null>(null);
  const [format, setFormat] = useState<MediaFormat>("mp4");
  const [quality, setQuality] = useState<MediaQuality>("best");
  const [audioQuality, setAudioQuality] = useState<AudioQuality>(192);
  const eventSourceRef = useRef<EventSource | null>(null);

  function closeEventSource() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }

  useEffect(() => () => closeEventSource(), []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedUrl = url.trim();

    if (!normalizedUrl) {
      setRequestState({
        status: "error",
        message: "Cole um link para começar a análise.",
      });
      return;
    }

    if (!isValidWebUrl(normalizedUrl)) {
      setRequestState({
        status: "error",
        message:
          "Use um endereço completo, como https://www.youtube.com/watch?v=...",
      });
      return;
    }

    setPreview(null);
    setQuality("best");
    setRequestState({
      status: "analyzing",
      message: "Consultando os metadados públicos do vídeo...",
    });

    try {
      const result = await analyzeMedia(normalizedUrl);
      setPreview(result.media);
      setRequestState({
        status: "ready",
        message: "Vídeo analisado. Escolha o formato e a qualidade do arquivo.",
      });
    } catch (error) {
      setRequestState({
        status: "error",
        message:
          error instanceof ApiRequestError
            ? error.message
            : "Ocorreu um erro inesperado. Tente novamente.",
      });
    }
  }

  async function retrieveReadyFile(job: DownloadJobState) {
    closeEventSource();
    setRequestState({
      status: "retrieving",
      message: "Arquivo pronto. Transferindo para o navegador...",
      jobId: job.job_id,
      job: { ...job, stage: "Transferindo arquivo pronto" },
      isCancelling: false,
    });

    try {
      const result = await downloadJobFile(job.job_id, format, preview?.title ?? "");
      setRequestState({
        status: "completed",
        message: `Download iniciado: ${result.filename}`,
      });
    } catch (error) {
      setRequestState({
        status: "error",
        message:
          error instanceof ApiRequestError
            ? error.message
            : "O arquivo ficou pronto, mas não pôde ser baixado.",
      });
    }
  }

  function handleJobUpdate(job: DownloadJobState) {
    if (job.status === "ready") {
      void retrieveReadyFile(job);
      return;
    }
    if (job.status === "failed") {
      closeEventSource();
      setRequestState({
        status: "error",
        message: job.error ?? "Não foi possível concluir o download.",
      });
      return;
    }
    if (job.status === "cancelled") {
      closeEventSource();
      setRequestState({ status: "cancelled", message: "Download cancelado." });
      return;
    }

    setRequestState({
      status: job.status,
      message:
        job.status === "processing"
          ? "Download concluído. Preparando o arquivo final..."
          : "Download em andamento...",
      jobId: job.job_id,
      job,
      isCancelling: false,
    });
  }

  async function handleDownload() {
    if (!preview || isActiveState(requestState)) {
      return;
    }

    let request: DownloadRequest;
    if (format === "mp4") {
      const selectedQuality =
        quality === "best"
          ? preview.qualities[0]
          : Number.parseInt(quality.replace(/p$/, ""), 10);

      if (!selectedQuality || !preview.qualities.includes(selectedQuality)) {
        setRequestState({
          status: "error",
          message: "Escolha uma qualidade de vídeo disponível antes de baixar.",
        });
        return;
      }
      request = {
        url: preview.original_url,
        format: "mp4",
        quality: selectedQuality,
      };
    } else {
      request = {
        url: preview.original_url,
        format: "mp3",
        audio_quality: audioQuality,
      };
    }

    try {
      const created = await createDownloadJob(request);
      const queuedJob: DownloadJobState = {
        job_id: created.job_id,
        status: "queued",
        stage: "Preparing",
        progress: null,
        downloaded_bytes: null,
        total_bytes: null,
        speed: null,
        eta: null,
        filename: null,
        mime_type: null,
        error: null,
        created_at: new Date().toISOString(),
        completed_at: null,
      };
      setRequestState({
        status: "queued",
        message: "Download adicionado à fila...",
        jobId: created.job_id,
        job: queuedJob,
        isCancelling: false,
      });

      eventSourceRef.current = subscribeToDownloadJob(created.job_id, {
        onUpdate: handleJobUpdate,
        onConnectionError: () => {
          closeEventSource();
          void cancelDownloadJob(created.job_id).catch(() => undefined);
          setRequestState((current) =>
            isActiveState(current) && current.jobId === created.job_id
              ? {
                  status: "error",
                  message:
                    "A conexão de progresso foi interrompida. Tente novamente.",
                }
              : current,
          );
        },
      });
    } catch (error) {
      setRequestState({
        status: "error",
        message:
          error instanceof ApiRequestError
            ? error.message
            : "Não foi possível iniciar o download. Tente novamente.",
      });
    }
  }

  async function handleCancel() {
    if (!isActiveState(requestState) || requestState.status === "retrieving") {
      return;
    }

    const jobId = requestState.jobId;
    setRequestState({ ...requestState, isCancelling: true });
    try {
      await cancelDownloadJob(jobId);
      closeEventSource();
      setRequestState({ status: "cancelled", message: "Download cancelado." });
    } catch (error) {
      setRequestState({
        status: "error",
        message:
          error instanceof ApiRequestError
            ? error.message
            : "Não foi possível cancelar o download.",
      });
    }
  }

  const isAnalyzing = requestState.status === "analyzing";
  const activeState = isActiveState(requestState) ? requestState : null;
  const isBusy = isAnalyzing || activeState !== null;
  const messageColor =
    requestState.status === "error"
      ? "text-danger"
      : ["ready", "completed"].includes(requestState.status)
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
              disabled={isBusy}
              onChange={(event) => {
                setUrl(event.target.value);
                if (preview !== null) {
                  setPreview(null);
                  setQuality("best");
                  setAudioQuality(192);
                }
                setRequestState(INITIAL_STATE);
              }}
              placeholder="Cole um link do YouTube..."
              aria-describedby="url-feedback"
              aria-invalid={requestState.status === "error" && preview === null}
              className="h-12 min-w-0 flex-1 bg-transparent text-base text-foreground outline-none placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-70"
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
            ) : activeState ? (
              "Download em andamento"
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
            {requestState.message ||
              "A análise consulta somente metadados públicos do YouTube."}
          </p>
        </div>
      </form>

      {activeState && (
        <DownloadProgress
          job={activeState.job}
          isCancelling={activeState.isCancelling}
          canCancel={activeState.status !== "retrieving"}
          onCancel={handleCancel}
        />
      )}

      <MediaPreview
        data={preview}
        format={format}
        quality={quality}
        audioQuality={audioQuality}
        isLoading={isAnalyzing}
        isDownloading={activeState !== null}
        onDownload={handleDownload}
        onFormatChange={(nextFormat) => {
          setFormat(nextFormat);
          if (nextFormat === "mp4") {
            setQuality("best");
          } else {
            setAudioQuality(192);
          }
          if (preview) {
            setRequestState({
              status: "ready",
              message:
                nextFormat === "mp3"
                  ? "Escolha o bitrate para converter e baixar o MP3."
                  : "Escolha a resolução para baixar o MP4.",
            });
          }
        }}
        onAudioQualityChange={setAudioQuality}
        onQualityChange={setQuality}
      />
    </div>
  );
}
