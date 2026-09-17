import type {
  AnalyzeResponse,
  AvailableMediaFormat,
  MediaInfo,
} from "@/types/media";

export type ApiErrorKind = "invalid-url" | "unavailable" | "unexpected";

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
