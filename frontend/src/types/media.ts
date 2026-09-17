export type MediaPlatform = "youtube" | "unknown";

export type MediaFormat = "mp4" | "mp3";

export type MediaQuality = "best" | "1080p" | "720p" | "480p";

export interface AnalyzeResponse {
  success: boolean;
  platform: MediaPlatform;
  title: string;
  author: string;
  duration: number;
  thumbnail: string | null;
}

