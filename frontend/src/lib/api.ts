import type {
  AnalyzeResponse,
  AvailableMediaFormat,
  DownloadRequest,
  DownloadResult,
  MediaInfo,
} from "@/types/media";

export type ApiErrorKind =
  | "invalid-request"
  | "invalid-url"
  | "limit"
  | "unavailable"
  | "unexpected";

export class ApiRequestError extends Error {
  constructor(
    public readonly kind: ApiErrorKind,
    message: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000"
).replace(/\/+$/, "");

function isAnalyzeResponse(value: unknown): value is AnalyzeResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    candidate.success === true &&
    candidate.platform === "youtube" &&
    isMediaInfo(candidate.media)
  );
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function isAvailableMediaFormat(value: unknown): value is AvailableMediaFormat {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    typeof candidate.format_id === "string" &&
    (candidate.type === "video" || candidate.type === "audio") &&
    isNullableString(candidate.extension) &&
    isNullableNumber(candidate.quality) &&
    isNullableNumber(candidate.fps) &&
    isNullableNumber(candidate.bitrate) &&
    isNullableNumber(candidate.filesize)
  );
}

function isMediaInfo(value: unknown): value is MediaInfo {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    typeof candidate.id === "string" &&
    typeof candidate.title === "string" &&
    isNullableString(candidate.author) &&
    isNullableNumber(candidate.duration) &&
    isNullableString(candidate.thumbnail) &&
    typeof candidate.original_url === "string" &&
    Array.isArray(candidate.qualities) &&
    candidate.qualities.every(
      (quality) => typeof quality === "number" && Number.isFinite(quality),
    ) &&
    Array.isArray(candidate.formats) &&
    candidate.formats.every(isAvailableMediaFormat)
  );
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const payload: unknown = await response.json();

    if (typeof payload !== "object" || payload === null) {
      return null;
    }

    const detail = (payload as Record<string, unknown>).detail;
    return typeof detail === "string" ? detail : null;
  } catch {
    return null;
  }
}

function errorFromResponse(response: Response, detail: string | null) {
  if (response.status === 413) {
    return new ApiRequestError(
      "limit",
      detail ?? "Este vídeo excede o limite atual de download do ClipFlow.",
    );
  }

  if (response.status === 400 || response.status === 422) {
    return new ApiRequestError(
      "invalid-request",
      detail ?? "Confira o link e as opções selecionadas.",
    );
  }

  if ([403, 404, 502, 503].includes(response.status)) {
    return new ApiRequestError(
      "unavailable",
      detail ?? "O vídeo não pôde ser processado neste momento.",
    );
  }

  return new ApiRequestError(
    "unexpected",
    detail ?? "Algo não saiu como esperado. Tente novamente em instantes.",
  );
}

function safeFilename(value: string, fallback: string): string {
  const leafName = value.split(/[\\/]/).at(-1) ?? "";
  const cleaned = leafName
    .replace(/[\u0000-\u001f\u007f<>:"|?*]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 180);

  return cleaned || fallback;
}

function filenameFromDisposition(
  contentDisposition: string | null,
  fallback: string,
): string {
  if (!contentDisposition) {
    return fallback;
  }

  const encodedMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    try {
      return safeFilename(decodeURIComponent(encodedMatch[1].trim()), fallback);
    } catch {
      return fallback;
    }
  }

  const plainMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1]
    ? safeFilename(plainMatch[1].trim(), fallback)
    : fallback;
}

function startBrowserDownload(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.hidden = true;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}

export async function analyzeMedia(url: string): Promise<AnalyzeResponse> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 30_000);
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
      signal: controller.signal,
    });
  } catch {
    throw new ApiRequestError(
      "unavailable",
      "Não foi possível falar com a API. Verifique se o backend está em execução.",
    );
  } finally {
    window.clearTimeout(timeoutId);
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);

    if (response.status === 400 || response.status === 422) {
      throw new ApiRequestError(
        "invalid-url",
        detail ?? "Esse link não parece válido. Confira o endereço e tente novamente.",
      );
    }

    if ([403, 404, 502, 503].includes(response.status)) {
      throw new ApiRequestError(
        "unavailable",
        detail ?? "O vídeo não pôde ser analisado neste momento.",
      );
    }

    throw new ApiRequestError(
      "unexpected",
      detail ?? "Algo não saiu como esperado. Tente novamente em instantes.",
    );
  }

  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    throw new ApiRequestError(
      "unexpected",
      "A API retornou uma resposta que não pôde ser lida.",
    );
  }

  if (!isAnalyzeResponse(payload)) {
    throw new ApiRequestError(
      "unexpected",
      "A API retornou uma resposta inesperada.",
    );
  }

  return payload;
}

export async function downloadMedia(
  request: DownloadRequest,
  fallbackTitle: string,
): Promise<DownloadResult> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 15 * 60_000);

  try {
    const response = await fetch(`${API_BASE_URL}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw errorFromResponse(response, await readErrorDetail(response));
    }

    const blob = await response.blob();
    if (blob.size === 0) {
      throw new ApiRequestError(
        "unexpected",
        "O backend retornou um arquivo vazio. Tente novamente.",
      );
    }

    const expectedMediaType =
      request.format === "mp3" ? "audio/mpeg" : "video/mp4";
    const responseMediaType = response.headers
      .get("Content-Type")
      ?.split(";", 1)[0]
      .trim()
      .toLowerCase();
    if (responseMediaType && responseMediaType !== expectedMediaType) {
      throw new ApiRequestError(
        "unexpected",
        "O backend retornou um formato de arquivo inesperado.",
      );
    }

    const extension = request.format;
    const fallbackStem =
      fallbackTitle || (extension === "mp3" ? "clipflow-audio" : "clipflow-video");
    const fallbackFilename = safeFilename(
      `${fallbackStem}.${extension}`,
      `clipflow-${extension === "mp3" ? "audio" : "video"}.${extension}`,
    );
    const filename = filenameFromDisposition(
      response.headers.get("Content-Disposition"),
      fallbackFilename,
    );
    startBrowserDownload(blob, filename);

    return { filename };
  } catch (error) {
    if (error instanceof ApiRequestError) {
      throw error;
    }
    throw new ApiRequestError(
      "unavailable",
      "Não foi possível concluir o download. Verifique a conexão e o backend.",
    );
  } finally {
    window.clearTimeout(timeoutId);
  }
}
