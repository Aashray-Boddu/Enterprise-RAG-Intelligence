import re
import unicodedata


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", " ").replace("\u00a0", " ")
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r"(?m)^[ \t]*[-_]{3,}[ \t]*$", " ", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    # Remove repeated short header/footer lines that occur on multiple pages upstream.
    return "\n".join(lines).strip()


def remove_repeated_page_artifacts(pages: list[dict]) -> list[dict]:
    if len(pages) < 3:
        return pages
    counts: dict[str, int] = {}
    for page in pages:
        lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
        for line in set(lines[:2] + lines[-2:]):
            if len(line) <= 100:
                counts[line] = counts.get(line, 0) + 1
    repeated = {line for line, count in counts.items() if count >= max(3, len(pages) // 2)}
    result = []
    for page in pages:
        lines = [line.strip() for line in page["text"].splitlines()]
        filtered = [line for line in lines if line and line not in repeated]
        result.append({"page_number": page["page_number"], "text": "\n".join(filtered)})
    return result
