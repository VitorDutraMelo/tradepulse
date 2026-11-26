"""Remove private information from text before it is logged or returned."""

import re
from collections.abc import Iterable

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_TOKEN_PATTERN = re.compile(
    r"(?i)(ssid|token|password|passwd|secret|authorization|cookie)"
    r"([\"']?\s*[:=]\s*[\"']?)([^\s\"',}]+)"
)
_OTCHARTS_KEY_PATTERN = re.compile(r"otc_(?:live|test)_[A-Za-z0-9]+")


def redact(text: object, secrets: Iterable[str] = ()) -> str:
    """Return ``text`` with credentials, tokens and e-mail addresses removed."""

    value = str(text)

    for secret in secrets:
        if secret and len(secret) >= 3:
            value = value.replace(secret, "[REDACTED]")

    value = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    value = _TOKEN_PATTERN.sub(r"\1\2[REDACTED]", value)
    value = _OTCHARTS_KEY_PATTERN.sub("[REDACTED_KEY]", value)

    return value
