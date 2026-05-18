# PDF-OCR

> Local web app that turns any PDF (including scans and password-protected files) into a searchable PDF + TXT / Markdown / DOCX / JSON-with-word-positions.
>
> Lokalna aplikacja web, która z dowolnego PDF-a (w tym skanów i plików chronionych hasłem) robi przeszukiwalny PDF + TXT / Markdown / DOCX / JSON z pozycjami słów.

---

## 🇵🇱 Po polsku

### Co to jest

Samodzielnie hostowana aplikacja do OCR plików PDF. Działa w 100% lokalnie — nic nie wycieka do chmury. Backend FastAPI + frontend Next.js. Wrzucasz PDF przez przeglądarkę, wybierasz formaty wyjściowe, a po skończonej pracy pobierasz wyniki.

### Funkcje

- **Dwa silniki OCR:**
  - `OCRmyPDF` (Tesseract) — szybki, dobrze rozpoznaje typowe dokumenty, wbudowane języki: polski, angielski, niemiecki, francuski, hiszpański, rosyjski.
  - `PaddleOCR` — lepsza jakość na trudnych skanach, opcjonalnie z CUDA.
- **PDF zabezpieczone hasłem** — wbudowany unlock (jeśli znasz hasło).
- **Formaty wyjściowe:** przeszukiwalny PDF, TXT, Markdown, DOCX, JSON z pozycjami słów (do dalszej obróbki).
- **Równoległość per-strona** — wykorzystuje wszystkie rdzenie CPU (lub GPU dla Paddle).
- **Bez limitu stron**, max upload 200 MB (konfigurowalne).
- **Auto-czyszczenie** — wyniki znikają godzinę po skończeniu jobu.
- **Wbudowany system backupów** (`tool/gxbk.py`) — szybkie zrzuty stanu projektu z opisem.

### Wymagania systemowe (Manjaro / Arch)

```bash
sudo pacman -S tesseract \
  tesseract-data-pol tesseract-data-eng tesseract-data-deu \
  tesseract-data-fra tesseract-data-spa tesseract-data-rus \
  ghostscript unpaper poppler nodejs pnpm python uv
# Opcjonalnie dla CUDA:
sudo pacman -S cuda cudnn
```

### Instalacja i uruchomienie

```bash
cp .env.example .env
make install        # uv sync + pnpm install
make dev            # backend :8114 + frontend :3101
# otwórz http://127.0.0.1:3101
```

CUDA: `cd backend && uv sync --extra gpu`.

### Testy

```bash
make test           # pytest + vitest (49 backend + 10 frontend)
make test-e2e       # Playwright
```

### Stack techniczny

- **Backend:** Python 3.11+, FastAPI, uvicorn, pypdf, pdf2image, pikepdf, pdfplumber, OCRmyPDF, PaddleOCR, ReportLab, python-docx
- **Frontend:** Next.js 15, React 19, Tailwind 4, shadcn/ui, Playwright (e2e), Vitest
- **Toolchain:** `uv` (Python), `pnpm` (Node)

---

## 🇬🇧 In English

### What it is

Self-hosted PDF OCR web app. Runs fully locally — nothing leaves your machine. FastAPI backend + Next.js frontend. Upload a PDF in the browser, pick output formats, download the results when the job finishes.

### Features

- **Two OCR engines:**
  - `OCRmyPDF` (Tesseract) — fast, solid on typical documents. Bundled languages: Polish, English, German, French, Spanish, Russian.
  - `PaddleOCR` — higher quality on hard scans, optional CUDA acceleration.
- **Password-protected PDFs** — built-in unlock (if you have the password).
- **Output formats:** searchable PDF, TXT, Markdown, DOCX, JSON with word positions (for downstream processing).
- **Per-page parallelism** — uses all CPU cores (or GPU with Paddle).
- **No page limit**, 200 MB max upload (configurable).
- **Auto cleanup** — job results are wiped 1 hour after completion.
- **Built-in backup system** (`tool/gxbk.py`) — quick project snapshots with descriptions.

### System dependencies (Manjaro / Arch)

```bash
sudo pacman -S tesseract \
  tesseract-data-pol tesseract-data-eng tesseract-data-deu \
  tesseract-data-fra tesseract-data-spa tesseract-data-rus \
  ghostscript unpaper poppler nodejs pnpm python uv
# Optional for CUDA:
sudo pacman -S cuda cudnn
```

### Install & run

```bash
cp .env.example .env
make install        # uv sync + pnpm install
make dev            # backend :8114 + frontend :3101
# open http://127.0.0.1:3101
```

For CUDA: `cd backend && uv sync --extra gpu`.

### Tests

```bash
make test           # pytest + vitest (49 backend + 10 frontend)
make test-e2e       # Playwright
```

### Tech stack

- **Backend:** Python 3.11+, FastAPI, uvicorn, pypdf, pdf2image, pikepdf, pdfplumber, OCRmyPDF, PaddleOCR, ReportLab, python-docx
- **Frontend:** Next.js 15, React 19, Tailwind 4, shadcn/ui, Playwright (e2e), Vitest
- **Toolchain:** `uv` (Python), `pnpm` (Node)

---

## Troubleshooting

- **`tesseract: command not found`** — install Tesseract and the language packs above.
- **`pdf2image` errors** — make sure `poppler` is installed (`pacman -S poppler`).
- **PaddleOCR downloads on first run** — models (~100 MB per language) are cached under `~/.paddleocr/`.
- **CUDA not detected** — check `nvidia-smi`, install with `cd backend && uv sync --extra gpu`, restart the backend.
- **Port already in use** — change `API_PORT` / `FRONT_PORT` in `.env`.
- **Job stuck on "Downloading models"** — the first run per language takes ~1 minute; subsequent runs are instant.

## Limits

- Max upload: 200 MB
- Job timeout: 30 minutes
- Results auto-purged 1 hour after completion

## Project layout

```
backend/   FastAPI app (api, ocr engines, pipeline, formats)
frontend/  Next.js app (dropzone, options, progress, results)
docs/      Design notes & implementation plan
tool/      gxbk.py — backup manager
```

## License

No license specified yet — treat as "all rights reserved" until one is added.
