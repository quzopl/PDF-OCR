export type Engine = "ocrmypdf" | "paddle";
export type Device = "cpu" | "cuda";
export type Language = "pl" | "en" | "de" | "fr" | "es" | "ru";
export type OutputFormat = "pdf" | "txt" | "md" | "docx" | "json";
export type JobStatus = "pending" | "running" | "done" | "failed";
export type JobStage =
  | "queued"
  | "downloading_models"
  | "preprocessing"
  | "ocr"
  | "formatting"
  | "finished";

export interface SystemInfo {
  cpu: { count: number; model: string };
  ram: { total_gb: number; available_gb: number };
  gpu: {
    cuda_available: boolean;
    devices: Array<{ id: number; name: string; vram_gb: number; driver: string }>;
    paddle_gpu_installed: boolean;
  };
}

export interface UploadResponse {
  file_id: string;
  page_count: number;
  size_bytes: number;
  is_encrypted: boolean;
}

export interface Preprocess {
  deskew: boolean;
  denoise: boolean;
}

export interface JobRequest {
  file_id: string;
  engine: Engine;
  languages: Language[];
  page_range: [number, number];
  preprocess: Preprocess;
  formats: OutputFormat[];
  workers: number;
  device: Device;
}

export interface JobOutput {
  format: OutputFormat;
  url: string;
  size_bytes: number;
}

export interface JobState {
  job_id: string;
  status: JobStatus;
  stage: JobStage;
  progress_pct: number;
  pages_done: number;
  total_pages: number;
  active_workers: number;
  warnings: string[];
  error: { message: string; details: string | null } | null;
  outputs: JobOutput[];
}
