import re


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*[\"']?)([^\"'\s]+)"),
    re.compile(r"(?i)(secret\s*[=:]\s*[\"']?)([^\"'\s]+)"),
    re.compile(r"(?i)(token\s*[=:]\s*[\"']?)([^\"'\s]+)"),
    re.compile(r"(?i)(password\s*[=:]\s*[\"']?)([^\"'\s]+)"),
    re.compile(r"(gh[pousr]_[A-Za-z0-9_]+)"),
    re.compile(r"(github_pat_[A-Za-z0-9_]+)"),
    re.compile(r"(sk-[A-Za-z0-9]+)"),
]


def redact_secrets(text: str) -> str:
    if not text:
        return text

    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(_replace_match, redacted)
    return redacted


def _replace_match(match: re.Match[str]) -> str:
    if match.lastindex and match.lastindex > 1:
        return f"{match.group(1)}[REDACTED]"
    return "[REDACTED_SECRET]"

