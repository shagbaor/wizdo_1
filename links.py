"""Finding links in Telegram messages and formatting the bot's replies.

Nothing in this file talks to Telegram or the database, so it is easy to test.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from telegram import Message, MessageEntity

# Plain-text fallback for links Telegram did not mark up itself
# (for example in forwarded or bot-generated text).
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"'`]+", re.IGNORECASE)

# Characters that usually end a sentence rather than belong to a link.
_TRAILING_PUNCTUATION = ".,;:!?\"'»…"
_BRACKETS = {")": "(", "]": "[", "}": "{", ">": "<"}

# Ready-made formats admins can pick with /setformat.
FORMAT_PRESETS = {
    "hash": "#{n} {url}",
    "number": "{n}. {url}",
    "link": "Link {n}: {url}",
}
DEFAULT_FORMAT = FORMAT_PRESETS["hash"]
MAX_FORMAT_LENGTH = 100


@dataclass(frozen=True)
class FoundLink:
    url: str  # the link exactly as it should be reposted
    key: str  # normalised form, used to spot repeated URLs


def strip_trailing_punctuation(url: str) -> str:
    """Remove sentence punctuation and unbalanced closing brackets from the end."""
    while url:
        last = url[-1]
        if last in _TRAILING_PUNCTUATION:
            url = url[:-1]
        elif last in _BRACKETS and url.count(last) > url.count(_BRACKETS[last]):
            url = url[:-1]
        else:
            break
    return url


def normalize_url(url: str) -> str:
    """Return a comparison key so that e.g. "HTTPS://Example.com/" == "https://example.com"."""
    url = url.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.IGNORECASE):
        url = "https://" + url
    try:
        parts = urlsplit(url)
    except ValueError:
        return url.lower()
    scheme = parts.scheme.lower()
    if scheme == "http":
        scheme = "https"
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, host, path, parts.query, ""))


def extract_links(message: Message) -> list[FoundLink]:
    """Return every link in a message (text or media caption), in reading order.

    Uses Telegram's own link markup first, which also finds links hidden behind
    clickable text, then falls back to a pattern search for anything it missed.
    """
    text = message.text or message.caption or ""
    if message.text is not None:
        entities = message.parse_entities([MessageEntity.URL, MessageEntity.TEXT_LINK])
    else:
        entities = message.parse_caption_entities(
            [MessageEntity.URL, MessageEntity.TEXT_LINK]
        )

    positioned: list[tuple[int, str]] = []
    covered: list[tuple[int, int]] = []
    utf16 = text.encode("utf-16-le")

    for entity, entity_text in entities.items():
        # Entity offsets count UTF-16 units; work out the Python string position
        # so links stay in reading order and the fallback search below can skip
        # text Telegram already handled.
        start = len(utf16[: entity.offset * 2].decode("utf-16-le", errors="ignore"))
        covered.append((start, start + len(entity_text)))
        url = entity.url if entity.type == MessageEntity.TEXT_LINK else entity_text
        url = strip_trailing_punctuation((url or "").strip())
        if url:
            positioned.append((start, url))

    for match in _URL_RE.finditer(text):
        if any(start <= match.start() < end for start, end in covered):
            continue
        url = strip_trailing_punctuation(match.group(0))
        if url and url.lower() not in ("www", "www."):
            positioned.append((match.start(), url))

    positioned.sort(key=lambda item: item[0])
    return [FoundLink(url=url, key=normalize_url(url)) for _, url in positioned]


def validate_format(template: str) -> str | None:
    """Return an error message if the template can't be used, otherwise None."""
    if len(template) > MAX_FORMAT_LENGTH:
        return f"The format must be at most {MAX_FORMAT_LENGTH} characters."
    if "{url}" not in template:
        return "The format must contain {url}."
    try:
        template.format(n=1, url="https://example.com")
    except (KeyError, IndexError, ValueError):
        return "Only {n} and {url} may appear inside curly brackets."
    return None


def format_link(template: str, number: int, url: str) -> str:
    try:
        return template.format(n=number, url=url)
    except (KeyError, IndexError, ValueError):
        return DEFAULT_FORMAT.format(n=number, url=url)


def split_message(lines: list[str], limit: int = 4000) -> list[str]:
    """Join lines into as few messages as possible under Telegram's 4096-char limit."""
    chunks: list[str] = []
    current = ""
    for line in lines:
        line = line[:limit]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
