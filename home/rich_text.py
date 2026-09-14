from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

from django.core.exceptions import ValidationError


_ALLOWED_TAGS = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "del",
        "div",
        "em",
        "h2",
        "h3",
        "h4",
        "i",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "span",
        "strong",
        "u",
        "ul",
    }
)
_VOID_TAGS = frozenset({"br"})
_SKIP_TAGS = frozenset({"iframe", "object", "script", "style", "svg", "template"})
_ALLOWED_LINK_SCHEMES = frozenset({"http", "https", "mailto"})
_HTML_TAG_RE = re.compile(r"<\s*/?\s*[a-z][^>]*>", re.IGNORECASE)


def _plain_text_to_html(value: str) -> str:
    paragraphs = [
        part.strip()
        for part in re.split(r"\r?\n\s*\r?\n+", value.strip())
        if part.strip()
    ]
    if not paragraphs:
        return ""

    return "".join(
        f"<p>{html.escape(paragraph, quote=False).replace(chr(10), '<br>')}</p>"
        for paragraph in paragraphs
    )


def is_safe_article_url(value: str) -> bool:
    value = (value or "").strip()
    if not value or value.startswith("//"):
        return False
    parsed = urlparse(value)
    return not parsed.scheme or parsed.scheme.casefold() in _ALLOWED_LINK_SCHEMES


def validate_article_url(value: str) -> str:
    if not is_safe_article_url(value):
        raise ValidationError("فقط لینک‌های http، https، mailto یا لینک‌های داخلی مجاز هستند.")
    return value


class _RichTextSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self._skip_depth = 0

    @staticmethod
    def _safe_attributes(tag: str, attrs: list[tuple[str, str | None]]) -> str:
        if tag != "a":
            return ""

        safe_attrs: list[str] = []
        for name, value in attrs:
            name = name.casefold()
            if name == "href" and value and is_safe_article_url(value):
                safe_attrs.append(f'href="{html.escape(value.strip(), quote=True)}"')
            elif name == "title" and value:
                safe_attrs.append(f'title="{html.escape(value.strip(), quote=True)}"')
            elif name == "target" and value == "_blank":
                safe_attrs.append('target="_blank"')
            elif name == "rel" and value:
                rel_tokens = {
                    token
                    for token in value.split()
                    if token.casefold() in {"nofollow", "noopener", "noreferrer"}
                }
                if rel_tokens:
                    safe_attrs.append(f'rel="{" ".join(sorted(rel_tokens))}"')
        return f" {' '.join(safe_attrs)}" if safe_attrs else ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if self._skip_depth:
            if tag in _SKIP_TAGS:
                self._skip_depth += 1
            return
        if tag in _SKIP_TAGS:
            self._skip_depth = 1
            return
        if tag not in _ALLOWED_TAGS:
            return
        self.parts.append(f"<{tag}{self._safe_attributes(tag, attrs)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self._skip_depth:
            if tag in _SKIP_TAGS:
                self._skip_depth -= 1
            return
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self._skip_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._skip_depth:
            self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        return


def sanitize_rich_text(value: str | None) -> str:
    if not value:
        return ""
    value = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not value:
        return ""

    source = value if _HTML_TAG_RE.search(value) else _plain_text_to_html(value)
    parser = _RichTextSanitizer()
    parser.feed(source)
    parser.close()
    sanitized = "".join(parser.parts).strip()
    if not re.sub(r"<[^>]+>", "", sanitized).strip():
        return ""
    return sanitized
