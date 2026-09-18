export type MediaPlatform = "youtube" | "tiktok";

export type MediaFormat = "mp4" | "mp3";

export type MediaQuality = "best" | `${number}p`;

export const SUPPORTED_MP3_BITRATES = [128, 192, 256, 320] as const;

export type AudioQuality = (typeof SUPPORTED_MP3_BITRATES)[number];

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

export type DownloadRequest =
  | {
      url: string;
      format: "mp4";
      quality: number;
    }
  | {
      url: string;
      format: "mp3";
      audio_quality: AudioQuality;
    };

export interface DownloadResult {
  filename: string;
}

export type DownloadJobStatus =
  | "queued"
  | "downloading"
  | "processing"
  | "ready"
  | "failed"
  | "cancelled";

export interface DownloadJobCreated {
  job_id: string;
  status: "queued";
}

export interface DownloadJobState {
  job_id: string;
  platform: MediaPlatform;
  status: DownloadJobStatus;
  stage: string;
  progress: number | null;
  downloaded_bytes: number | null;
  total_bytes: number | null;
  speed: number | null;
  eta: number | null;
  filename: string | null;
  mime_type: "video/mp4" | "audio/mpeg" | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}
