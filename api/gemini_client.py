from google import genai

from api.config import settings

# One Client per process so we do not rebuild it on every HTTP request.
_gemini_client = genai.Client(api_key=settings.gemini_api_key)


def get_gemini_client():
    """Return the shared Google GenAI client (API key comes from settings)."""
    return _gemini_client
