"""
Gemini API retry helper with exponential backoff.

WHY WE RETRY TRANSIENT ERRORS BUT NOT QUOTA ERRORS:
----------------------------------------------------
HTTP 500 / 503 / 504 and UNAVAILABLE / 'high demand' errors are *transient*:
the server is momentarily overloaded or restarting, and the exact same request
will usually succeed within a few seconds.  Retrying is both safe and effective.

HTTP 429 / RESOURCE_EXHAUSTED is a *quota* error: the project has consumed its
daily or per-minute allowance.  Retrying immediately (or even after a few
seconds) cannot fix this — the quota does not refresh until the window resets
(up to 24 hours for daily limits).  Retrying would only waste time and add
confusing latency, so we raise 429 immediately and let the caller's existing
error handling decide what to do.
"""

import logging
import random
import time

logger = logging.getLogger(__name__)

# HTTP status codes / gRPC status strings that indicate a transient server-side problem.
_TRANSIENT_HTTP_CODES = {500, 503, 504}
_TRANSIENT_KEYWORDS = {"unavailable", "high demand"}  # checked case-insensitively

# HTTP status code / gRPC status string for quota exhaustion — raise immediately.
_QUOTA_KEYWORDS = {"429", "resource_exhausted", "resourceexhausted"}


def _is_transient(exc: Exception) -> bool:
    """Return True if *exc* looks like a transient server error worth retrying."""
    msg = str(exc).lower()

    # Check for quota errors first — these must NOT be retried.
    if any(kw in msg for kw in _QUOTA_KEYWORDS):
        return False

    # Check for well-known transient keywords.
    if any(kw in msg for kw in _TRANSIENT_KEYWORDS):
        return True

    # Check for numeric HTTP status codes embedded in the error message.
    if any(str(code) in msg for code in _TRANSIENT_HTTP_CODES):
        return True

    # Some SDK versions expose a .status_code or .code attribute.
    for attr in ("status_code", "code"):
        code = getattr(exc, attr, None)
        if code is not None and int(code) in _TRANSIENT_HTTP_CODES:
            return True

    return False


def _is_quota_error(exc: Exception) -> bool:
    """Return True if *exc* is a quota / rate-limit error that must not be retried."""
    msg = str(exc).lower()
    return any(kw in msg for kw in _QUOTA_KEYWORDS)


def generate_with_retry(gemini_client, model: str, contents, max_attempts: int = 3):
    """Call gemini_client.models.generate_content with exponential-backoff retries.

    Retry policy
    ------------
    - Retries ONLY on transient server errors: HTTP 500, 503, 504, or errors
      whose message contains 'UNAVAILABLE' or 'high demand'.
    - Does NOT retry on 429 / RESOURCE_EXHAUSTED — quota limits cannot be
      resolved by retrying; see module docstring for the full rationale.
    - Waits with exponential backoff: ~1 s, ~2 s, ~4 s (plus ±30 % random jitter)
      using time.sleep so the event loop is not blocked.
    - Logs a WARNING on each retry with the attempt number and error type.
    - Re-raises the last exception after all attempts are exhausted so the
      caller's existing try/except and fallback logic continues to work.

    Args:
        gemini_client: The shared ``genai.Client`` instance.
        model:         Model name string (e.g. ``"gemini-2.5-flash"``).
        contents:      Prompt string, list of parts, or any value accepted by
                       ``models.generate_content``.
        max_attempts:  Maximum total call attempts (default 3).

    Returns:
        The ``GenerateContentResponse`` returned by the API.

    Raises:
        The last exception if all retry attempts fail, or the original
        exception immediately if it is a quota / rate-limit error.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return gemini_client.models.generate_content(
                model=model,
                contents=contents,
            )
        except Exception as exc:
            # Quota errors are not recoverable — raise immediately.
            if _is_quota_error(exc):
                raise

            # Non-transient errors (e.g. invalid request, auth failure) — raise immediately.
            if not _is_transient(exc):
                raise

            last_exc = exc

            if attempt == max_attempts:
                # Final attempt failed; fall through to re-raise below.
                break

            # Exponential backoff: base delay doubles each attempt (1 s, 2 s, 4 s …),
            # plus ±30 % jitter so concurrent retries do not all hit the server together.
            base_delay = 2 ** (attempt - 1)  # 1, 2, 4 seconds
            jitter = base_delay * random.uniform(-0.3, 0.3)
            delay = max(0.1, base_delay + jitter)

            logger.warning(
                "[generate_with_retry] Transient error on attempt %d/%d (%s: %s). "
                "Retrying in %.1f s…",
                attempt,
                max_attempts,
                type(exc).__name__,
                exc,
                delay,
            )
            time.sleep(delay)

    # All attempts exhausted — re-raise so existing error handling still works.
    raise last_exc
