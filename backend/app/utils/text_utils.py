"""
app/utils/text_utils.py
────────────────────────
Shared text-processing helpers used across parsers, scorers, and generators.
"""

import re
import unicodedata
from typing import List, Set


def normalise_text(text: str) -> str:
    """
    Normalise unicode, collapse whitespace, strip control characters.
    Safe to call on any raw extracted text.
    """
    # Normalise unicode (e.g. curly quotes → straight, ligatures → letters)
    text = unicodedata.normalize("NFKD", text)
    # Drop non-printable control chars except newlines/tabs
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", " ", text)
    # Collapse runs of spaces/tabs (not newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Collapse 3+ newlines → 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenise_keywords(text: str, min_len: int = 2) -> List[str]:
    """
    Tokenise text into lowercase keywords, filtering stop words.
    Returns deduplicated list preserving first-seen order.
    """
    STOP = {
        "a","an","the","and","or","but","in","on","at","to","for","of",
        "with","by","from","as","is","it","be","are","was","were","have",
        "has","had","do","does","did","will","would","could","should","may",
        "might","we","our","us","your","their","this","that","these","those",
        "which","who","how","what","when","where","why","all","any","both",
        "each","not","no","so","if","than","then","just","also","about",
        "after","before","between","into","through","during","above","below",
    }
    tokens: List[str] = re.findall(r"\b[a-zA-Z][\w+#.-]*\b", text.lower())
    seen: Set[str] = set()
    result: List[str] = []
    for t in tokens:
        if t not in STOP and len(t) >= min_len and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def extract_years_of_experience(text: str) -> int:
    """
    Parse 'X+ years of experience' or 'X-Y years' from JD/resume text.
    Returns the minimum required years (0 if not found).
    """
    patterns = [
        r"(\d+)\+?\s*(?:to\s*\d+)?\s*years?\s*(?:of\s*)?(?:experience|exp)",
        r"minimum\s*(?:of\s*)?(\d+)\s*years?",
        r"at\s+least\s+(\d+)\s*years?",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0


def split_into_bullets(text: str) -> List[str]:
    """
    Split a block of text into individual bullet points.
    Handles:  • … | – … | * … | numbered lists | plain sentences
    """
    # Try bullet-based split first
    bullet_pattern = re.compile(r"^[\s]*[•\-–—*▪►✓✔]\s+", re.MULTILINE)
    if bullet_pattern.search(text):
        items = bullet_pattern.split(text)
    else:
        # Fall back to numbered list
        numbered = re.split(r"\n\d+[.)]\s+", text)
        if len(numbered) > 1:
            items = numbered
        else:
            # Fall back to sentence splitting on ". " or newlines
            items = re.split(r"(?<=[.!?])\s+|\n+", text)

    cleaned = []
    for item in items:
        item = item.strip().lstrip("•-–—*▪►✓✔0123456789.) ").strip()
        if item and len(item) > 10:
            cleaned.append(item)
    return cleaned


def truncate(text: str, max_chars: int = 200, suffix: str = "…") -> str:
    """Truncate text to max_chars at a word boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated + suffix


def count_action_verbs(text: str) -> int:
    """
    Count strong resume action verbs in text.
    Higher count → stronger, more impactful resume.
    """
    ACTION_VERBS = {
        "achieved","automated","built","collaborated","created","decreased",
        "delivered","designed","developed","drove","enhanced","engineered",
        "established","executed","generated","implemented","improved","increased",
        "launched","led","managed","mentored","optimised","optimized","reduced",
        "refactored","scaled","shipped","spearheaded","streamlined","transformed",
        "unified","upgraded","architected","authored","deployed","directed",
        "facilitated","founded","grew","integrated","invented","migrated",
        "modernised","modernized","negotiated","pioneered","produced","rebuilt",
        "restructured","revamped","shaped","solved","supervised","trained",
    }
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return len(words & ACTION_VERBS)


def sanitise_filename(name: str) -> str:
    """Make a string safe to use as a filename."""
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s]+", "_", name.strip())
    return name[:80]  # max 80 chars
