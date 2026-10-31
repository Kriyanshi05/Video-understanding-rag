# tests/test_retry.py
# Verifies that generate_with_retry() in retrieval/llm_utils.py:
#   - succeeds and returns the API response after two simulated 503 errors
#     (i.e. the third attempt works)
#   - raises immediately on a 429 / RESOURCE_EXHAUSTED error without any retry
#   - raises the original exception after exhausting max_attempts when every
#     attempt fails with a transient 503 error
#   - patches time.sleep so the tests run without real delays

import pytest
from unittest.mock import MagicMock, patch, call

from retrieval.llm_utils import generate_with_retry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _transient_503():
    """Return an exception that looks like an HTTP 503 Service Unavailable."""
    return RuntimeError("HTTP 503 Service Unavailable")


def _quota_429():
    """Return an exception that looks like a 429 RESOURCE_EXHAUSTED quota error."""
    return RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")


def _fake_client(side_effects):
    """
    Build a minimal fake gemini_client whose models.generate_content raises
    the items in *side_effects* in order; if a side effect is not an exception
    it is returned directly as the response.
    """
    client = MagicMock()
    responses = []
    for item in side_effects:
        if isinstance(item, Exception):
            responses.append(item)
        else:
            responses.append(item)

    call_count = {"n": 0}

    def _generate_content(model, contents):  # noqa: ARG001
        i = call_count["n"]
        call_count["n"] += 1
        effect = responses[i]
        if isinstance(effect, BaseException):
            raise effect
        return effect

    client.models.generate_content.side_effect = _generate_content
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSuccessAfterTransientErrors:
    """Succeeds on the third attempt after two 503 failures; sleep is called twice."""

    def test_returns_response_after_two_503_errors(self):
        fake_response = MagicMock(text="answer text")
        client = _fake_client([_transient_503(), _transient_503(), fake_response])

        with patch("retrieval.llm_utils.time.sleep") as mock_sleep:
            result = generate_with_retry(client, model="gemini-test", contents="q")

        assert result is fake_response
        assert client.models.generate_content.call_count == 3
        # sleep must have been called exactly twice (once after attempt 1, once after attempt 2)
        assert mock_sleep.call_count == 2

    def test_sleep_delay_is_positive(self):
        """The delay passed to sleep must be > 0 on both retries."""
        fake_response = MagicMock(text="ok")
        client = _fake_client([_transient_503(), _transient_503(), fake_response])

        sleep_delays = []
        with patch("retrieval.llm_utils.time.sleep", side_effect=lambda d: sleep_delays.append(d)):
            generate_with_retry(client, model="gemini-test", contents="q")

        assert all(d > 0 for d in sleep_delays), f"Non-positive delay found: {sleep_delays}"

    def test_first_attempt_success_no_sleep(self):
        """When the first attempt succeeds, sleep is never called."""
        fake_response = MagicMock(text="immediate")
        client = _fake_client([fake_response])

        with patch("retrieval.llm_utils.time.sleep") as mock_sleep:
            result = generate_with_retry(client, model="gemini-test", contents="q")

        assert result is fake_response
        mock_sleep.assert_not_called()


class TestQuotaErrorRaisedImmediately:
    """429 / RESOURCE_EXHAUSTED must be re-raised on the first attempt without retry."""

    def test_429_raises_without_retry(self):
        quota_err = _quota_429()
        client = _fake_client([quota_err])

        with patch("retrieval.llm_utils.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError, match="RESOURCE_EXHAUSTED"):
                generate_with_retry(client, model="gemini-test", contents="q")

        # Only one call — no retry attempted
        assert client.models.generate_content.call_count == 1
        mock_sleep.assert_not_called()

    def test_429_after_one_transient_still_raises_immediately(self):
        # Attempt 1 → 503 (transient, would retry), Attempt 2 → 429 (quota, must stop)
        client = _fake_client([_transient_503(), _quota_429()])

        with patch("retrieval.llm_utils.time.sleep"):
            with pytest.raises(RuntimeError, match="RESOURCE_EXHAUSTED"):
                generate_with_retry(client, model="gemini-test", contents="q")

        # Two calls total (attempt 1 then attempt 2), no attempt 3
        assert client.models.generate_content.call_count == 2

    def test_resource_exhausted_string_raises_immediately(self):
        # Alternate casing / phrasing still detected
        err = RuntimeError("resource_exhausted: daily quota hit")
        client = _fake_client([err])

        with patch("retrieval.llm_utils.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError):
                generate_with_retry(client, model="gemini-test", contents="q")

        mock_sleep.assert_not_called()


class TestMaxAttemptsExhausted:
    """After max_attempts all failing with 503, the last exception is re-raised."""

    def test_raises_after_three_503_failures(self):
        errs = [_transient_503(), _transient_503(), _transient_503()]
        client = _fake_client(errs)

        with patch("retrieval.llm_utils.time.sleep"):
            with pytest.raises(RuntimeError, match="503"):
                generate_with_retry(client, model="gemini-test", contents="q", max_attempts=3)

        assert client.models.generate_content.call_count == 3

    def test_sleep_called_max_attempts_minus_one_times(self):
        # With max_attempts=3 and all failures: sleep after attempt 1 and 2 (not after 3)
        client = _fake_client([_transient_503(), _transient_503(), _transient_503()])
        sleep_calls = []

        with patch("retrieval.llm_utils.time.sleep", side_effect=lambda d: sleep_calls.append(d)):
            with pytest.raises(RuntimeError):
                generate_with_retry(client, model="gemini-test", contents="q", max_attempts=3)

        assert len(sleep_calls) == 2

    def test_custom_max_attempts_respected(self):
        # max_attempts=1 → no retry, fails immediately on first 503
        client = _fake_client([_transient_503()])

        with patch("retrieval.llm_utils.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError, match="503"):
                generate_with_retry(client, model="gemini-test", contents="q", max_attempts=1)

        assert client.models.generate_content.call_count == 1
        mock_sleep.assert_not_called()

    def test_raises_last_exception_not_first(self):
        # Each attempt raises a distinct exception; the last one should propagate
        err1 = RuntimeError("503 first transient")
        err2 = RuntimeError("503 second transient")
        err3 = RuntimeError("503 third transient — the last one")
        client = _fake_client([err1, err2, err3])

        with patch("retrieval.llm_utils.time.sleep"):
            with pytest.raises(RuntimeError, match="third transient — the last one"):
                generate_with_retry(client, model="gemini-test", contents="q", max_attempts=3)


class TestNonTransientErrorRaisedImmediately:
    """Errors that are neither quota nor transient (e.g. auth) must not be retried."""

    def test_auth_error_raises_without_retry(self):
        auth_err = RuntimeError("401 Unauthorized: invalid API key")
        client = _fake_client([auth_err])

        with patch("retrieval.llm_utils.time.sleep") as mock_sleep:
            with pytest.raises(RuntimeError, match="Unauthorized"):
                generate_with_retry(client, model="gemini-test", contents="q")

        assert client.models.generate_content.call_count == 1
        mock_sleep.assert_not_called()
