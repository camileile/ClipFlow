export type MediaPlatform = "youtube";

export type MediaFormat = "mp4" | "mp3";

export type MediaQuality = "best" | `${number}p`;

export interface AvailableMediaFormat {
  format_id: string;
  type: "video" | "audio";
  extension: string | null;
  quality: number | null;
  fps: number | null;
  bitrate: number | null;
  filesize: number | null;
}

export interface MediaInfo {
  id: string;
  title: string;
  author: string | null;
  duration: number | null;
  thumbnail: string | null;
  original_url: string;
  qualities: number[];
  formats: AvailableMediaFormat[];
}

export interface AnalyzeResponse {
  success: true;
  platform: MediaPlatform;
  media: MediaInfo;
}
