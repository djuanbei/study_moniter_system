"""OCR services.

Two backends are supported:
  - pytesseract (default, local; needs the `tesseract` binary)
  - a vision-capable LLM (OpenAI / Anthropic) for handwritten or difficult
    images. Use is controlled by `OCR_USE_VISION` and falls back gracefully.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image

from app.config import get_settings


logger = logging.getLogger(__name__)


def _preprocess(path: Path) -> Image.Image:
    img = Image.open(path)
    if img.mode != "L":
        img = img.convert("L")
    # Resize to a sane upper bound to help OCR.
    max_side = 1800
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))
    return img


def ocr_with_tesseract(path: Path) -> str:
    try:
        import pytesseract
    except ImportError:
        logger.warning("pytesseract not installed; OCR unavailable")
        return ""
    try:
        img = _preprocess(path)
        return pytesseract.image_to_string(img, lang="chi_sim+eng")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tesseract failed for %s: %s", path, exc)
        return ""


def ocr_with_vision(path: Path) -> str:
    """Use a vision-capable LLM for OCR. Optional; gated by OCR_USE_VISION."""
    settings = get_settings()
    if not settings.openai_api_key:
        return ""
    try:
        import base64

        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        data = base64.b64encode(path.read_bytes()).decode("ascii")
        llm = ChatOpenAI(
            model=settings.vision_model or settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            temperature=0.0,
            max_tokens=2000,
        )
        msg = HumanMessage(
            content=[
                {"type": "text", "text": "请准确转写图片中的全部手写/印刷文本，保持原顺序，不要添加解释。"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}},
            ]
        )
        result = llm.invoke([msg])
        return result.content if isinstance(result.content, str) else str(result.content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vision OCR failed for %s: %s", path, exc)
        return ""


def ocr_image(path: Path | str) -> str:
    settings = get_settings()
    path = Path(path)
    if settings.ocr_use_vision:
        text = ocr_with_vision(path)
        if text:
            return text
    return ocr_with_tesseract(path)


def ocr_pdf(path: Path | str, page_limit: int = 10) -> str:
    """Try to OCR each page of a PDF; returns combined text."""
    path = Path(path)
    try:
        from pdf2image import convert_from_path
    except ImportError:
        logger.warning("pdf2image not installed; cannot OCR PDF")
        return ""
    try:
        pages = convert_from_path(str(path), dpi=200, last_page=page_limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF->image failed for %s: %s", path, exc)
        return ""
    out: list[str] = []
    for i, page in enumerate(pages):
        buf = io.BytesIO()
        page.save(buf, format="PNG")
        tmp = path.with_suffix(f".page{i}.png")
        try:
            tmp.write_bytes(buf.getvalue())
            out.append(ocr_image(tmp))
        finally:
            if tmp.exists():
                tmp.unlink()
    return "\n\n".join(t for t in out if t)