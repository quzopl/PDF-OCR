import type {
  JobRequest,
  JobState,
  OutputFormat,
  SystemInfo,
  UploadResponse,
} from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8114";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init);
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const body = await r.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await r.json()) as T;
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/api/upload", { method: "POST", body: form });
}

export async function unlockPdf(file_id: string, password: string): Promise<UploadResponse> {
  return request<UploadResponse>("/api/unlock", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id, password }),
  });
}

export async function createJob(req: JobRequest): Promise<{ job_id: string }> {
  return request("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function getJob(id: string): Promise<JobState> {
  return request<JobState>(`/api/jobs/${id}`);
}

export function downloadUrl(id: string, fmt: OutputFormat): string {
  return `${BASE}/api/jobs/${id}/download/${fmt}`;
}

export async function getSystemInfo(): Promise<SystemInfo> {
  return request<SystemInfo>("/api/system/info");
}
