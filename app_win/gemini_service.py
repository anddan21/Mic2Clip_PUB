"""Gemini API: polish text and translate."""

from __future__ import annotations

import logging

import config

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai

    _genai = genai
except ImportError:
    _genai = None


def _ensure_configured() -> bool:
    if not config.GEMINI_API_KEY or not _genai:
        return False
    _genai.configure(api_key=config.GEMINI_API_KEY)
    return True


def polish_text(text: str) -> str:
    """Fix grammar, punctuation, and light style; same language as input (no translation)."""
    if not text.strip():
        return text
    if not _ensure_configured():
        logger.warning("Gemini not configured (set GEMINI_API_KEY in .env).")
        return text
    model = _genai.GenerativeModel(config.GEMINI_MODEL)
    prompt = (
        "You are an editor. Improve grammar, punctuation, and clarity of the following text. "
        "Do not translate or change the language: the output must be in the same language as the input. "
        "Return ONLY the improved text, no quotes or explanations.\n\n"
        f"{text}"
    )
    response = model.generate_content(prompt)
    out = (response.text or "").strip()
    return out if out else text


def translate_text(text: str, target_language: str) -> str:
    if not text.strip():
        return text
    if not _ensure_configured():
        logger.warning("Gemini not configured (set GEMINI_API_KEY in .env).")
        return text
    model = _genai.GenerativeModel(config.GEMINI_MODEL)
    prompt = (
        f"Translate the following text to {target_language}. "
        f"Return ONLY the translation, no quotes or explanations.\n\n{text}"
    )
    response = model.generate_content(prompt)
    out = (response.text or "").strip()
    return out if out else text
