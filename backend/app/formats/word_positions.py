from __future__ import annotations

import json
from pathlib import Path

from app.ocr.base import OcrResult


def write_word_positions_json(result: OcrResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.json"
    data = {
        "engine": result.engine,
        "languages": result.languages,
        "pages": [
            {
                "page_number": p.page_number,
                "width": p.width,
                "height": p.height,
                "words": [
                    {"text": w.text, "bbox": list(w.bbox), "confidence": w.confidence}
                    for w in p.words
                ],
            }
            for p in result.pages
        ],
    }
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
