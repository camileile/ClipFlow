"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { DownloadProgress } from "@/components/download-progress";
import {
  ArrowRightIcon,
  CheckIcon,
  ClipFlowIcon,
  LinkIcon,
} from "@/components/icons";
import { MediaPreview } from "@/components/media-preview";
import {
  RetroWindow,
  type RetroTabId,
} from "@/components/retro-window";
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
  MediaPlatform,
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
  const [activeTab, setActiveTab] = useState<RetroTabId>("downloader");
  const [url, setUrl] = useState("");
  const [requestState, setRequestState] = useState<RequestState>(INITIAL_STATE);
  const [preview, setPreview] = useState<MediaInfo | null>(null);
  const [previewPlatform, setPreviewPlatform] = useState<MediaPlatform | null>(null);
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
          "Use um endereço completo do YouTube ou TikTok.",
      });
      return;
    }

    setPreview(null);
    setPreviewPlatform(null);
    setQuality("best");
    setRequestState({
      status: "analyzing",
      message: "Consultando os metadados públicos do vídeo...",
    });

    try {
      const result = await analyzeMedia(normalizedUrl);
      setPreview(result.media);
      setPreviewPlatform(result.platform);
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
        platform: previewPlatform ?? "youtube",
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
      : requestState.status === "cancelled"
        ? "text-warning"
      : ["ready", "completed"].includes(requestState.status)
        ? "text-success-strong"
        : "text-muted";

  const statusText =
    requestState.status === "idle"
      ? "Pronto"
      : requestState.status === "analyzing"
        ? "Lendo informações da mídia..."
        : requestState.message;
  const statusTone =
    requestState.status === "error"
      ? "danger"
      : requestState.status === "cancelled"
        ? "warning"
      : ["ready", "completed"].includes(requestState.status)
        ? "success"
        : isBusy
          ? "busy"
          : "default";

  const feedbackTitle =
    requestState.status === "error"
      ? "Erro"
      : requestState.status === "cancelled"
        ? "Cancelado"
        : requestState.status === "completed"
          ? "Concluído"
          : requestState.status === "ready"
            ? "Pronto"
            : requestState.status === "analyzing"
              ? "Analisando"
              : "Informação";
  const feedbackSymbol =
    requestState.status === "error"
      ? "!"
      : requestState.status === "cancelled"
        ? "×"
        : ["ready", "completed"].includes(requestState.status)
          ? "✓"
          : "i";

  const activityDetails = activeState
    ? [
        ["Job", `${activeState.job.job_id.slice(0, 8)}…`],
        ["Plataforma", activeState.job.platform === "tiktok" ? "TikTok" : "YouTube"],
        ["Formato", format.toUpperCase()],
        [
          "Qualidade",
          format === "mp4"
            ? quality === "best"
              ? `${preview?.qualities[0] ?? "—"}p`
              : quality
            : `${audioQuality} kbps`,
        ],
        ["Arquivo", activeState.job.filename ?? "Em preparação"],
      ]
    : [];

  return (
    <RetroWindow
      activeTab={activeTab}
      onTabChange={setActiveTab}
      statusText={statusText}
      statusTone={statusTone}
    >
      {activeTab === "downloader" && (
        <div className="space-y-3">
          <section className="retro-group" aria-labelledby="source-title">
            <h2 id="source-title" className="retro-group-title">
              <LinkIcon className="size-4 text-accent-strong" />
              Fonte
            </h2>
            <div className="retro-group-body">
              <form onSubmit={handleSubmit} noValidate>
                <label
                  htmlFor="media-url"
                  className="mb-1.5 block text-[13px] font-bold text-foreground"
                >
                  URL da mídia:
                </label>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
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
                        setPreviewPlatform(null);
                        setQuality("best");
                        setAudioQuality(192);
                      }
                      setRequestState(INITIAL_STATE);
                    }}
                    placeholder="Cole um link do YouTube ou TikTok..."
                    aria-describedby="url-feedback"
                    aria-invalid={requestState.status === "error" && preview === null}
                    className="retro-inset h-10 min-w-0 flex-1 px-3 text-sm outline-none placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-65"
                  />
                  <button
                    type="submit"
                    disabled={isBusy}
                    className="retro-button retro-button-primary flex h-10 min-w-32 items-center justify-center gap-2 px-5"
                  >
                    {isAnalyzing ? (
                      <>
                        <span className="size-3 animate-pulse border border-white bg-white/40" />
                        Analisando...
                      </>
                    ) : activeState ? (
                      "Em andamento"
                    ) : (
                      <>
                        Analisar
                        <ArrowRightIcon className="size-4" />
                      </>
                    )}
                  </button>
                </div>
                <div
                  className={`retro-alert mt-2.5 min-h-9 px-2.5 py-2 ${
                    requestState.status === "error"
                      ? "retro-alert-danger"
                      : requestState.status === "cancelled"
                        ? "retro-alert-warning"
                      : ["ready", "completed"].includes(requestState.status)
                        ? "retro-alert-success"
                        : ""
                  }`}
                  aria-live="polite"
                >
                  <div className="flex items-start gap-2">
                    <span className="retro-alert-icon" aria-hidden="true">
                      {feedbackSymbol}
                    </span>
                    <p id="url-feedback" className={`min-w-0 text-[13px] leading-5 ${messageColor}`}>
                      <strong className="mr-1 text-foreground">{feedbackTitle}:</strong>
                      {requestState.message ||
                        "Insira um link público do YouTube ou TikTok para ler as informações da mídia."}
                    </p>
                  </div>
                </div>
              </form>
            </div>
          </section>

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
            platform={previewPlatform}
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
      )}

      {activeTab === "activity" && (
        <section className="retro-group" aria-labelledby="activity-title">
          <h2 id="activity-title" className="retro-group-title">
            Atividade atual
          </h2>
          <div className="retro-group-body min-h-[340px] sm:min-h-[470px]">
            {activeState ? (
              <div className="space-y-3">
                <DownloadProgress
                  job={activeState.job}
                  isCancelling={activeState.isCancelling}
                  canCancel={activeState.status !== "retrieving"}
                  onCancel={handleCancel}
                />
                <dl className="retro-inset grid grid-cols-[minmax(110px,0.35fr)_1fr] text-[13px]">
                  {activityDetails.map(([label, value]) => (
                    <div key={label} className="contents">
                      <dt className="border-b border-line bg-surface-elevated px-3 py-2 font-bold">
                        {label}
                      </dt>
                      <dd className="min-w-0 border-b border-line px-3 py-2 font-mono">
                        {value}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : (
              <div className="retro-inset grid min-h-52 place-items-center p-6 text-center">
                <div>
                  <span className="mx-auto mb-3 grid size-10 place-items-center border border-line-strong bg-surface-elevated text-success-strong">
                    <CheckIcon className="size-5" />
                  </span>
                  <p className="font-bold">Nenhum download ativo.</p>
                  <p className="mt-1 text-[13px] text-muted">
                    Inicie uma operação na aba Downloader para acompanhar o job aqui.
                  </p>
                  {requestState.message && (
                    <p className="mt-4 border-t border-line pt-3 text-[13px] text-muted">
                      Último evento: {requestState.message}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {activeTab === "about" && (
        <section className="retro-group" aria-labelledby="about-title">
          <h2 id="about-title" className="retro-group-title">
            Sobre o ClipFlow
          </h2>
          <div className="retro-group-body min-h-[340px] sm:min-h-[470px]">
            <div className="retro-inset mx-auto max-w-2xl p-5 sm:p-7">
              <div className="flex items-start gap-4 border-b border-line pb-5">
                <span className="retro-app-icon size-12">
                  <ClipFlowIcon className="size-6" />
                </span>
                <div>
                  <h2 className="text-xl font-bold text-foreground">ClipFlow</h2>
                  <p className="mt-1 font-mono text-[12px] text-muted">
                    Media Download Utility · Version 0.6
                  </p>
                </div>
              </div>
              <p className="mt-5 text-sm leading-6">
                Uma ferramenta direta para analisar vídeos públicos do YouTube e TikTok e
                preparar arquivos MP4 ou MP3 com progresso real, velocidade, ETA
                e cancelamento.
              </p>
              <dl className="mt-5 grid gap-2 text-[13px] sm:grid-cols-2">
                <div className="border border-line bg-surface-elevated p-3">
                  <dt className="font-bold">Plataforma</dt>
                  <dd className="mt-1 text-muted">YouTube e TikTok</dd>
                </div>
                <div className="border border-line bg-surface-elevated p-3">
                  <dt className="font-bold">Formatos</dt>
                  <dd className="mt-1 text-muted">MP4 e MP3</dd>
                </div>
                <div className="border border-line bg-surface-elevated p-3">
                  <dt className="font-bold">Processamento</dt>
                  <dd className="mt-1 text-muted">yt-dlp + FFmpeg</dd>
                </div>
                <div className="border border-line bg-surface-elevated p-3">
                  <dt className="font-bold">Conexão</dt>
                  <dd className="mt-1 text-muted">Jobs temporários via SSE</dd>
                </div>
              </dl>
              <p className="mt-5 border-l-4 border-accent bg-accent-soft px-4 py-3 text-[13px] leading-5 text-foreground">
                Use o ClipFlow somente para conteúdo que você tenha permissão ou
                direito de baixar.
              </p>
            </div>
          </div>
        </section>
      )}
    </RetroWindow>
  );
}
