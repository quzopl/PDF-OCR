# OCR PDF — Design Spec

**Date:** 2026-05-16
**Status:** Approved (brainstorming phase)
**Owner:** quzopl

## 1. Goal

A local web application with a polished GUI that performs OCR on a single PDF file. The user uploads one PDF, picks an engine and options, and downloads results in one or more formats.

Scope is intentionally narrow: one document at a time, no auth, no multi-user, no persistent storage beyond temporary working files.

## 2. Functional requirements

- **Input:** one PDF file per job, up to 200 MB / 500 pages.
- **OCR engines (user-selectable):**
  - **OCRmyPDF** (Tesseract under the hood) — native searchable PDF output.
  - **PaddleOCR** — neural OCR with native word-level bounding boxes.
- **Languages (user picks any subset, multi-select):** Polish, English, German, French, Spanish, Russian.
- **Page range:** user picks `[start, end]` (1-indexed, both ends inclusive) from a slider populated with the actual page count of the uploaded file.
- **Preprocessing toggles:** deskew, denoise. For OCRmyPDF these map to the engine's built-in flags; for PaddleOCR we apply them ourselves via OpenCV before passing pages to the engine.
- **Output formats (user picks any subset):**
  - Searchable PDF (image + invisible text layer).
  - Plain text (`.txt`).
  - Markdown (`.md`) — paragraphs separated by blank lines, pages separated by `---`.
  - Word (`.docx`) — page break per source page, paragraphs as text blocks.
  - JSON with word positions — list of pages, each with words `{text, bbox, confidence}`.
- **Workers (parallelism within one document):** user-selectable, default = `cpu_count`. Max = `cpu_count` (overridable via `OCR_MAX_WORKERS` env var). User takes responsibility for RAM consequences.
- **Hardware acceleration:** if CUDA is available and `paddlepaddle-gpu` is installed, the UI offers a `CUDA / CPU` toggle for the PaddleOCR engine. OCRmyPDF (Tesseract) is CPU-only and ignores this toggle.
- **Hardware info chip:** the app auto-detects CPU count, RAM, and GPU at startup and shows a small chip in the header (e.g. `🖥 16 CPU · 32 GB RAM · 🟢 CUDA RTX 3060`).

## 3. Non-functional requirements

- **Local only.** Backend binds to `127.0.0.1`. No authentication.
- **No persistent storage.** Job state lives in an in-memory dict; working files live under `/tmp/ocrapp/<job_id>/` and are cleaned by a TTL sweeper (default 1 h after job completion).
- **Resilience to engine crashes.** Worker processes that die do not bring down the API; the affected job is marked `FAILED` with the exception detail.
- **Progress reporting.** UI sees `pages_done / total_pages` updates within ~1 s of each page completing.

## 4. Architecture

```
┌─────────────────────┐        HTTP/JSON         ┌──────────────────────┐
│  Next.js 15 (App)   │ ◄──────────────────────► │  FastAPI (uvicorn)   │
│  React + shadcn/ui  │                          │  Python 3.11+        │
│  port 3101          │                          │  port 8114           │
└─────────────────────┘                          └──────────┬───────────┘
                                                            │
                                       ┌────────────────────┼────────────────────┐
                                       ▼                    ▼                    ▼
                              ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐
                              │ OCRmyPDF engine │  │ PaddleOCR engine│  │ Temp store +   │
                              │ (subprocess)    │  │ (in-process)    │  │ in-mem jobs    │
                              └─────────────────┘  └─────────────────┘  └────────────────┘
```

- Frontend and backend are separate processes. Frontend talks to backend via `fetch` (REST + 1 s polling for job status).
- Job state is held in a thread-safe in-memory dict in the FastAPI process. Server restart drops jobs (acceptable for local use).
- Per-job working directory under `/tmp/ocrapp/<job_id>/`. TTL cleanup runs in a background asyncio task.
- OCRmyPDF runs as a subprocess (its Python API is a thin wrapper over its CLI). PaddleOCR is called as a Python library.

## 5. Backend

### 5.1 Layout

```
backend/
├── pyproject.toml                  # uv, ruff, optional [gpu] extra
├── app/
│   ├── main.py                     # FastAPI app, CORS for :3101, lifespan
│   ├── config.py                   # paths, TTL, limits
│   ├── system_info.py              # CPU/RAM/GPU detection (cached)
│   ├── api/
│   │   ├── upload.py               # POST /api/upload
│   │   ├── jobs.py                 # POST/GET /api/jobs[/id]
│   │   ├── download.py             # GET /api/jobs/{id}/download/{format}
│   │   └── system.py               # GET /api/system/info
│   ├── jobs/
│   │   ├── store.py                # in-memory dict + lock + TTL cleanup
│   │   └── models.py               # JobStatus, JobResult (pydantic)
│   ├── ocr/
│   │   ├── base.py                 # OcrEngine ABC + OcrResult dataclasses
│   │   ├── ocrmypdf_engine.py
│   │   └── paddle_engine.py
│   ├── pipeline/
│   │   ├── preprocess.py           # deskew/denoise (before Paddle)
│   │   ├── page_range.py           # extract page subset from PDF
│   │   └── runner.py               # range → preprocess → engine → formatters
│   └── formats/
│       ├── searchable_pdf.py
│       ├── text.py
│       ├── markdown.py
│       ├── docx.py
│       └── word_positions.py
└── tests/
    ├── fixtures/
    └── test_*.py
```

### 5.2 REST endpoints

| Method | Path | Body / Result |
|---|---|---|
| `GET`  | `/api/system/info` | `{ cpu: {count, model}, ram: {total_gb, available_gb}, gpu: { cuda_available, devices: [{id, name, vram_gb, driver}], paddle_gpu_installed } }` |
| `POST` | `/api/upload` | multipart PDF → `{ file_id, page_count, size_bytes }` |
| `POST` | `/api/jobs` | `{ file_id, engine: "ocrmypdf"\|"paddle", languages: [...], page_range: [start, end], preprocess: {deskew, denoise}, formats: [...], workers: int, device: "cuda"\|"cpu" }` → `{ job_id }` |
| `GET`  | `/api/jobs/{id}` | `{ status: "pending"\|"running"\|"done"\|"failed", stage: "queued"\|"downloading_models"\|"preprocessing"\|"ocr"\|"formatting", progress_pct, pages_done, total_pages, active_workers, warnings?: string[], error?: {message, details}, outputs?: [{format, url, size_bytes}] }` |
| `GET`  | `/api/jobs/{id}/download/{format}` | streams the output file |

No `DELETE` — auto cleanup only.

### 5.3 Internal OCR representation

```python
@dataclass
class Word:
    text: str
    bbox: tuple[float, float, float, float]   # x0,y0,x1,y1 in PDF points
    confidence: float | None

@dataclass
class OcrPage:
    page_number: int                          # 1-indexed in the original PDF
    width: float
    height: float
    words: list[Word]

@dataclass
class OcrResult:
    pages: list[OcrPage]
    engine: str
    languages: list[str]
    raw_searchable_pdf: Path | None           # set when engine produces one natively
```

Engines populate `OcrResult`. Formatters consume only this interface, so format logic is engine-agnostic.

### 5.4 Pipeline

```
1. extract_page_range(input.pdf, [start, end]) → working.pdf            # pypdf
2. if engine == "paddle" and (deskew or denoise):
       pages_png = render(working.pdf, dpi=300)                         # pdf2image
       pages_png = [preprocess(p, deskew, denoise) for p in pages_png]  # opencv
   else:
       (OCRmyPDF handles its own preprocessing via --deskew --clean)
3. result = engine.run(working.pdf | pages_png, opts, progress_cb)
       # progress_cb fires after every completed page → updates job store
4. outputs = {fmt: FORMATTERS[fmt](result, output_dir) for fmt in requested_formats}
5. job.outputs = outputs; job.status = DONE
```

### 5.5 Workers and CUDA

- Job options carry `workers: int` and `device: "cuda" | "cpu"`.
- **OCRmyPDF** → `--jobs <workers>`; `device` ignored.
- **PaddleOCR + CPU** → `concurrent.futures.ProcessPoolExecutor(max_workers=workers)`, each process initializes its own `PaddleOCR` instance.
- **PaddleOCR + CUDA** → a single `PaddleOCR(use_gpu=True)` instance. With one GPU, concurrent `predict` calls serialize on the device, so the worker count provides at best modest CUDA-stream overlap. The runner uses `ThreadPoolExecutor(max_workers=min(workers, 2))` for CUDA and surfaces a warning when the user-selected `workers` is silently capped this way.
- **CUDA fallback:** if `device == "cuda"` but CUDA initialization fails at runtime, the runner logs a warning, switches to CPU, appends a message to the job's `warnings` array, and completes the job normally (this is not a failure).

### 5.6 Engine × format matrix

| Format | OCRmyPDF | PaddleOCR |
|---|---|---|
| Searchable PDF | native (`--output-type pdf`) | overlay: `reportlab` draws invisible text on rasters, `pikepdf` merges over originals |
| Plain TXT | `--sidecar text.txt` | `\n`.join words/lines per page |
| Markdown | from TXT, blank line between blocks, `---` between pages | grouped into lines/paragraphs by bbox coordinates |
| DOCX | `python-docx`: paragraph per block, page break per page | same, with paragraphs split using bbox-derived line groups |
| JSON positions | `pdfplumber` extracts words from the produced text layer | native — Paddle returns `[(bbox, (text, conf)), ...]` per page |

Notes:
- Searchable PDF for Paddle uses the **original** rasters, not the preprocessed/whitened ones — the user gets a readable source document with a text layer on top.
- DPI for rendering = 300. Not exposed to the UI in MVP.
- Page numbering in MD/DOCX/JSON outputs reflects the **original** PDF page numbers (e.g. if the user picks pages 10–20, the output shows page 10, page 11, …).

## 6. Frontend

### 6.1 Layout

```
frontend/
├── package.json                    # next 15, react 19, tailwind 4, shadcn
├── components.json
├── app/
│   ├── layout.tsx                  # ThemeProvider, Toaster (sonner), Inter font
│   ├── page.tsx                    # single-page flow
│   └── globals.css
├── components/
│   ├── ui/                         # shadcn primitives
│   ├── hardware-chip.tsx           # header chip from /api/system/info
│   ├── dropzone.tsx                # react-dropzone + framer-motion
│   ├── job-options.tsx             # engine, languages, range, preprocess, formats, workers, device
│   ├── progress-panel.tsx          # progress bar + pages_done / total + active_workers
│   ├── results-panel.tsx           # download buttons per output
│   └── engine-info.tsx             # tooltips
├── lib/
│   ├── api.ts                      # fetch wrappers, BASE_URL from env
│   ├── types.ts
│   └── format-matrix.ts            # validation: which engine × format combos are sensible
└── hooks/
    └── use-job-status.ts           # polls GET /api/jobs/{id} every 1 s with abort
```

### 6.2 Flow

One page, sections appear progressively as the user advances:

```
┌────────────────────────────────────────────────────┐
│  OCR PDF                     🖥 16 CPU · 32 GB · 🟢 │  ← header + hw chip + theme toggle
├────────────────────────────────────────────────────┤
│  [1] Drop PDF here                                 │  ← large dropzone, hover animation
├────────────────────────────────────────────────────┤
│  [2] Options                                       │  ← appears after upload
│   Engine    ◉ OCRmyPDF   ◯ PaddleOCR               │
│   Languages ☑ PL ☑ EN ☐ DE ☐ FR ☐ ES ☐ RU         │
│   Pages     [1] ─●────●─── [42]                    │  ← slider populated from page_count
│   Preproc   ☑ Deskew  ☑ Denoise                    │
│   Formats   ☑ PDF ☑ TXT ☐ MD ☑ DOCX ☐ JSON         │
│   Workers   [Auto (16) ▼]                          │
│   Device    ◉ CUDA (RTX 3060)  ◯ CPU               │  ← only when applicable
│   [ Start OCR ]                                    │
├────────────────────────────────────────────────────┤
│  [3] Progress                                      │  ← after Start
│   ▓▓▓▓▓▓▓▓▓░░░░  62%  18 / 29 pages  · 4 workers   │
├────────────────────────────────────────────────────┤
│  [4] Download                                      │  ← after completion
│   [⬇ PDF]  [⬇ TXT]  [⬇ DOCX]                       │
└────────────────────────────────────────────────────┘
```

### 6.3 UX details

- Dark mode default, theme toggle in the header.
- Hardware chip is clickable and opens a popover with full `system_info` details.
- Cross-validation in `format-matrix.ts`: incompatible/lossy combinations show a subtle warning ("JSON positions from OCRmyPDF are extracted from the text layer — less precise") but are not blocked.
- Model-download stage (`stage === "downloading_models"`) shows a labeled progress message instead of pages-done.
- Errors surface via `sonner` toasts; a collapsible "Show details" exposes the backend traceback for power users.
- Framer-motion animates the reveal of each new section.
- No PDF preview in MVP (intentionally out of scope).

## 7. Error handling

| Situation | Backend behavior | User-visible |
|---|---|---|
| Not a PDF on upload | 400 | toast "Not a PDF" |
| Encrypted PDF, can't unlock | 422 | toast "PDF is password-protected" |
| Corrupt / 0 pages | 422 (validated by `pypdf` at upload) | toast "Could not open PDF" |
| Over size / page limit | 413 / 422 | toast with the limit |
| Missing Paddle model | Paddle auto-downloads; job stage = `downloading_models` | progress message "Downloading models…" |
| OOM (RAM or VRAM) | Worker catches, marks `FAILED` | toast "Out of memory — reduce workers or switch to CPU" |
| CUDA selected but unavailable at runtime | Falls back to CPU, job continues, appends to `warnings[]` | toast "GPU unavailable, ran on CPU" |
| Engine raises exception | `status=FAILED`, `error={message, details}` | error card with collapsible details |
| Job > 30 min | Killed, `status=FAILED, error="Timeout"` | toast + retry button |

All errors go to `logs/app.log` (JSON via `structlog`).

## 8. Testing

### Backend (pytest)

- `tests/fixtures/`:
  - `text_pl.pdf` — 2-page Polish scan
  - `mixed.pdf` — text page + scanned page
  - `multipage.pdf` — 10 pages
  - `encrypted.pdf` — password-protected
- `test_ocr_engines.py` — parametrized: every engine × every fixture → asserts known words appear in `OcrResult`.
- `test_formats.py` — every formatter on a synthetic `OcrResult`; validates PDF structure (pikepdf), DOCX content, JSON parsability.
- `test_api.py` — `TestClient` smoke test of the full flow.
- `test_page_range.py` — page subset extraction and output numbering.
- `test_workers.py` — `workers > 1` produces the same `OcrResult.pages` content as `workers = 1`.

### Frontend

- Vitest unit tests for `lib/format-matrix.ts` and `lib/api.ts`.
- One Playwright smoke test: upload fixture PDF → default options → wait for `done` → click download TXT → assert content.

## 9. Setup & packaging

### System dependencies (Manjaro / Arch)

```bash
sudo pacman -S tesseract \
               tesseract-data-pol tesseract-data-eng \
               tesseract-data-deu tesseract-data-fra \
               tesseract-data-spa tesseract-data-rus \
               ghostscript unpaper poppler nodejs python uv
# optional for CUDA:
sudo pacman -S cuda cudnn
```

### Repo layout

```
ocr/
├── README.md
├── Makefile                # make dev / make test / make install
├── .env.example            # OCR_MAX_WORKERS, FRONT_PORT=3101, API_PORT=8114, ...
├── backend/                # FastAPI (section 5)
├── frontend/               # Next.js (section 6)
└── docs/
    └── superpowers/
        └── specs/
```

### Python deps (`backend/pyproject.toml`)

- Base: `fastapi`, `uvicorn`, `python-multipart`, `pypdf`, `pdf2image`, `pikepdf`, `pdfplumber`, `python-docx`, `opencv-python-headless`, `numpy`, `psutil`, `structlog`, `ocrmypdf`, `paddleocr`, `paddlepaddle`.
- Optional `[project.optional-dependencies] gpu = ["paddlepaddle-gpu"]`.

### Frontend deps (`frontend/package.json`)

- `next@15`, `react@19`, `tailwindcss@4`, `shadcn/ui`, `framer-motion`, `react-dropzone`, `sonner`, `lucide-react`.

### Running

- `make dev` — runs `uvicorn` on `:8114` and `pnpm dev -p 3101` in parallel with prefixed logs.
- `make test` — runs `pytest` and `playwright test`.
- No Docker in MVP. CUDA passthrough complicates Docker meaningfully and the app is intended for local desktop use.

## 10. Out of scope (MVP)

- Batch / queue of multiple files (single document only).
- PDF preview in the browser.
- User accounts, sharing, multi-tenant.
- Persistent job history beyond the in-memory store.
- Cloud OCR engines (Google, Azure, AWS).
- DPI control in the UI (hardcoded 300).
- Heading / table / form structure recovery in MD/DOCX outputs (paragraph-level only).
