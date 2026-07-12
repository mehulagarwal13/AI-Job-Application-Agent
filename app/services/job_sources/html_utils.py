"""Minimal HTML-to-text for job descriptions (Remotive/Arbeitnow return HTML)."""

import html
import re

_TAG = re.compile(r"<[^>]+>")
_BLOCK_TAGS = re.compile(r"</?(p|br|div|li|ul|ol|h[1-6]|tr)[^>]*>", re.IGNORECASE)


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = _BLOCK_TAGS.sub("\n", raw)   # keep paragraph structure as newlines
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
