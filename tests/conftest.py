# conftest.py — sets the minimum environment variables required to import
# api.config (which validates settings at module load time) before any test
# module is collected.  This avoids the "gemini_api_key field required" error
# without touching any source file or needing a real .env.

import os

# Provide a dummy API key so pydantic-settings validation passes.
# Tests that actually exercise Gemini behaviour use a fake client object, so
# this value is never sent to the network.
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-pytest")
