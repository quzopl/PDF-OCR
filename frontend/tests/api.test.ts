import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { uploadPdf, unlockPdf, createJob, getJob, downloadUrl, getSystemInfo } from "@/lib/api";

const originalFetch = global.fetch;

describe("api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    global.fetch = originalFetch;
  });

  it("uploads a PDF", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ file_id: "abc", page_count: 3, size_bytes: 100, is_encrypted: false }),
    });
    const file = new File([new Uint8Array([1, 2, 3])], "x.pdf", { type: "application/pdf" });
    const r = await uploadPdf(file);
    expect(r.page_count).toBe(3);
    expect(r.is_encrypted).toBe(false);
    expect((global.fetch as any).mock.calls[0][0]).toMatch(/\/api\/upload$/);
  });

  it("unlocks a PDF with password", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ file_id: "abc", page_count: 5, size_bytes: 200, is_encrypted: false }),
    });
    const r = await unlockPdf("abc", "secret");
    expect(r.is_encrypted).toBe(false);
    expect(r.page_count).toBe(5);
    expect((global.fetch as any).mock.calls[0][0]).toMatch(/\/api\/unlock$/);
    const body = JSON.parse((global.fetch as any).mock.calls[0][1].body);
    expect(body).toEqual({ file_id: "abc", password: "secret" });
  });

  it("creates a job", async () => {
    (global.fetch as any).mockResolvedValue({ ok: true, json: async () => ({ job_id: "j" }) });
    const r = await createJob({
      file_id: "f",
      engine: "ocrmypdf",
      languages: ["pl"],
      page_range: [1, 2],
      preprocess: { deskew: true, denoise: false },
      formats: ["txt"],
      workers: 2,
      device: "cpu",
    });
    expect(r.job_id).toBe("j");
  });

  it("gets job status", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        job_id: "j",
        status: "running",
        stage: "ocr",
        progress_pct: 50,
        pages_done: 1,
        total_pages: 2,
        active_workers: 1,
        warnings: [],
        error: null,
        outputs: [],
      }),
    });
    const r = await getJob("j");
    expect(r.status).toBe("running");
  });

  it("builds download URL", () => {
    expect(downloadUrl("j", "pdf")).toMatch(/\/api\/jobs\/j\/download\/pdf$/);
  });

  it("fetches system info", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        cpu: { count: 8, model: "X" },
        ram: { total_gb: 16, available_gb: 8 },
        gpu: { cuda_available: false, devices: [], paddle_gpu_installed: false },
      }),
    });
    const r = await getSystemInfo();
    expect(r.cpu.count).toBe(8);
  });

  it("throws on non-ok response", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "bad" }),
    });
    await expect(getJob("x")).rejects.toThrow(/bad/);
  });
});
