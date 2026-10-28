"""Remove credentials from provider errors before they reach logs or artifacts."""
import re


def redact_error(value):
    if value is None:
        return None
    return re.sub(r"(?i)((?:api[_-]?key|access[_-]?token|token|authorization|password)=)[^&\s'\"<>]+", r"\1[REDACTED]", str(value))
