import type { AnalyzeResponse } from "@/types/media";

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
    typeof candidate.success === "boolean" &&
    (candidate.platform === "youtube" || candidate.platform === "unknown") &&
    typeof candidate.title === "string" &&
    typeof candidate.author === "string" &&
    typeof candidate.duration === "number" &&
    (candidate.thumbnail === null || typeof candidate.thumbnail === "string")
  );
}

export async function analyzeMedia(url: string): Promise<AnalyzeResponse> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 10_000);
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

  if (response.status === 422) {
    throw new ApiRequestError(
      "invalid-url",
      "Esse link não parece válido. Confira o endereço e tente novamente.",
    );
  }

  if (!response.ok) {
    throw new ApiRequestError(
      "unexpected",
      "Algo não saiu como esperado. Tente novamente em instantes.",
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
